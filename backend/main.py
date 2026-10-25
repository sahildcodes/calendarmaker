import os
import shutil
import tempfile
import json
import uuid
import secrets
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel

from backend.ocr_service import (
    OCRService,
    ImageSecurityError,
    DecompressionBombError,
    InvalidImageError,
    CorruptedImageError,
    OCRTimeoutError,
    OCRProcessingError
)
from backend.parser_service import EventParserService
from backend.conflict_advisor import ConflictAdvisorService
from backend.calendar_service import CalendarService
from backend import metrics_service
from backend.security import (
    sign_session_id,
    verify_session_id,
    process_image_limiter,
    admin_limiter,
    verify_admin_password
)

app = FastAPI(
    title="Image-to-Calendar API",
    description="Secure full-stack application converting screenshots of assignments, schedules, and event flyers into validated Google Calendar events.",
    version="1.0.0"
)

# ---------------------------------------------------------------------------
# 1. CORS Configuration (Restricted - No Wildcard)
# ---------------------------------------------------------------------------
allowed_origins_env = os.environ.get("ALLOWED_ORIGINS", "").strip()
if allowed_origins_env:
    allowed_origins = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]
else:
    allowed_origins = [
        "http://localhost:8080",
        "http://127.0.0.1:8080"
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# 2. Security Headers Middleware
# ---------------------------------------------------------------------------
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(self), microphone=(), geolocation=()"
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "img-src 'self' data: blob:; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "script-src 'self' 'unsafe-inline'; "
        "connect-src 'self'; "
        "frame-ancestors 'none';"
    )
    return response

# ---------------------------------------------------------------------------
# 3. Signed Session Middleware
# ---------------------------------------------------------------------------
@app.middleware("http")
async def session_middleware(request: Request, call_next):
    raw_cookie = request.cookies.get("session_id")
    session_id = verify_session_id(raw_cookie)
    new_session = False

    if not session_id:
        session_id = str(uuid.uuid4())
        new_session = True
    request.state.session_id = session_id

    # Record unique visitor analytics
    try:
        metrics_service.record_visitor(session_id)
    except Exception:
        pass

    response = await call_next(request)
    if new_session:
        signed_cookie = sign_session_id(session_id)
        is_secure = request.url.scheme == "https" or os.environ.get("PRODUCTION", "").lower() == "true"
        response.set_cookie(
            key="session_id",
            value=signed_cookie,
            httponly=True,
            samesite="lax",
            secure=is_secure,
            max_age=60 * 60 * 24 * 30  # 30 days
        )
    return response

# ---------------------------------------------------------------------------
# 4. Admin Credentials Initialization
# ---------------------------------------------------------------------------
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "").strip()
if not ADMIN_PASSWORD:
    if os.environ.get("PRODUCTION", "").lower() == "true":
        raise RuntimeError("ADMIN_PASSWORD must be configured when PRODUCTION=true")
    ADMIN_PASSWORD = secrets.token_urlsafe(24)
    print(f"[SECURITY] No ADMIN_PASSWORD provided in environment. Generated secure temporary admin token: {ADMIN_PASSWORD}")

# Initialize Core Services
ocr_service = OCRService()
parser_service = EventParserService()
conflict_advisor = ConflictAdvisorService()
calendar_service = CalendarService(data_dir=os.path.join(os.path.dirname(__file__), "..", "data"))

# Pydantic Schemas
class EventValidationRequest(BaseModel):
    event: Dict[str, Any]

class EventSubmissionRequest(BaseModel):
    events: List[Dict[str, Any]]

# ---------------------------------------------------------------------------
# 5. API Endpoints
# ---------------------------------------------------------------------------
@app.get("/api/health")
def health_check(request: Request):
    session_id = getattr(request.state, "session_id", None)
    return {
        "status": "healthy",
        "ocr_available": ocr_service.tesseract_available,
        "google_authenticated": calendar_service.is_google_authenticated(session_id)
    }

@app.get("/api/calendar/status")
def get_calendar_status(request: Request):
    session_id = getattr(request.state, "session_id", None)
    is_auth = calendar_service.is_google_authenticated(session_id)
    profile = calendar_service.get_user_profile(session_id)
    events = calendar_service.get_calendar_events(session_id=session_id)
    has_creds = calendar_service.has_client_credentials()
    source = calendar_service.get_credentials_source()

    return {
        "authenticated": is_auth,
        "mode": "google_calendar" if is_auth else "sandbox",
        "email": profile.get("email") if is_auth else None,
        "has_credentials": has_creds,
        "credentials_source": source,
        "total_calendar_events": len(events)
    }

@app.get("/api/calendar/auth-url")
def get_google_auth_url(request: Request, redirect_uri: Optional[str] = None):
    """Generates the Google OAuth 2.0 authorization URL for user login."""
    if not calendar_service.has_client_credentials():
        raise HTTPException(status_code=400, detail="Google OAuth credentials are not configured on the server.")

    # Determine default redirect URI based on PUBLIC_URL or current request host
    if not redirect_uri:
        public_url = os.environ.get("PUBLIC_URL", "").strip().rstrip('/')
        if public_url:
            base = public_url
        else:
            base = str(request.base_url).rstrip('/')
            if "127.0.0.1:8080" in base:
                base = base.replace("127.0.0.1:8080", "localhost:8080")
        redirect_uri = f"{base}/api/calendar/oauth-callback"

    try:
        res = calendar_service.get_auth_url(redirect_uri)
        return {
            "auth_url": res["auth_url"],
            "state": res["state"],
            "redirect_uri": redirect_uri
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to initialize Google authentication.")

@app.get("/api/calendar/oauth-callback")
def google_oauth_callback(request: Request, code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None):
    """Handles Google OAuth redirect with authorization code and establishes user session."""
    if error:
        return RedirectResponse(url=f"/?auth=error&msg=Authentication+declined")
    if not code:
        return RedirectResponse(url="/?auth=error&msg=No+authorization+code+received")

    public_url = os.environ.get("PUBLIC_URL", "").strip().rstrip('/')
    if public_url:
        base = public_url
    else:
        base = str(request.base_url).rstrip('/')
        if "127.0.0.1:8080" in base:
            base = base.replace("127.0.0.1:8080", "localhost:8080")
    redirect_uri = f"{base}/api/calendar/oauth-callback"
    session_id = getattr(request.state, "session_id", None)

    try:
        calendar_service.handle_oauth_callback(code, redirect_uri, session_id=session_id, state=state)
        return RedirectResponse(url="/?auth=success")
    except Exception as e:
        print(f"[OAUTH ERROR] Callback failed: {e}")
        return RedirectResponse(url="/?auth=error&msg=Authentication+failed")

@app.post("/api/calendar/disconnect")
def disconnect_google_account(request: Request):
    """Disconnects Google account, revokes OAuth access with Google, and clears local tokens."""
    session_id = getattr(request.state, "session_id", None)
    calendar_service.disconnect_google(session_id=session_id)
    return {
        "success": True,
        "mode": "sandbox",
        "message": "Google Account disconnected and tokens revoked. Reverted to Calendar Sandbox."
    }

@app.get("/api/calendar/events")
def list_calendar_events(request: Request, start_date: Optional[str] = None, end_date: Optional[str] = None):
    session_id = getattr(request.state, "session_id", None)
    events = calendar_service.get_calendar_events(start_date, end_date, session_id=session_id)
    return {"events": events, "count": len(events)}

MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB

@app.post("/api/process-image")
async def process_image_upload(request: Request, file: UploadFile = File(...)):
    """
    Hardened Image-to-Calendar processing pipeline:
    1. Rate limits upload frequency (5 scans/min per session/IP).
    2. Enforces strict 10 MB upload ceiling via chunked streaming.
    3. Generates isolated UUID temporary paths.
    4. Reconstructs image via Pillow, verifying format, dimensions, and stripping metadata.
    5. Runs OCR with 10-second timeout.
    6. Parses, sanitizes, validates, and checks schedule conflicts.
    7. Guarantees temp file cleanup.
    """
    session_id = getattr(request.state, "session_id", "anon")
    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"{session_id}:{client_ip}"

    # Rate limiting
    if not process_image_limiter.is_allowed(rate_key, max_requests=5, window_seconds=60):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Maximum 5 image scans allowed per minute. Please wait before scanning again."
        )

    # Fast header check for payload size
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_UPLOAD_SIZE:
                raise HTTPException(status_code=413, detail="File too large. Maximum allowed size is 10 MB.")
        except ValueError:
            pass

    # Create isolated temp directory with UUID filenames
    temp_dir = tempfile.mkdtemp()
    raw_path = os.path.join(temp_dir, f"raw_{uuid.uuid4().hex}")
    sanitized_path = os.path.join(temp_dir, f"sanitized_{uuid.uuid4().hex}.png")

    try:
        # Stream read with continuous byte counting
        total_bytes = 0
        with open(raw_path, "wb") as buffer:
            while chunk := await file.read(64 * 1024):  # 64 KB chunks
                total_bytes += len(chunk)
                if total_bytes > MAX_UPLOAD_SIZE:
                    raise HTTPException(status_code=413, detail="File exceeds maximum allowed upload size of 10 MB.")
                buffer.write(chunk)

        if total_bytes == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        # 1. Format verification, decompression bomb check, and RGB reconstruction
        try:
            ocr_service.validate_and_reconstruct_image(raw_path, sanitized_path)
        except DecompressionBombError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except InvalidImageError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except CorruptedImageError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except ImageSecurityError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            print(f"[IMAGE VALIDATION ERROR] {e}")
            raise HTTPException(status_code=400, detail="Image could not be validated.")

        # 2. OCR Extraction with timeout
        try:
            ocr_result = ocr_service.process_image(sanitized_path)
        except OCRTimeoutError:
            raise HTTPException(status_code=504, detail="OCR processing timed out. Please try a clearer or smaller image.")
        except OCRProcessingError as e:
            raise HTTPException(status_code=422, detail=f"Text recognition failed on this image: {str(e)}")
        except Exception as e:
            print(f"[OCR ERROR] {e}")
            raise HTTPException(status_code=422, detail="Text recognition failed.")

        # 3. Parsing Event Objects
        try:
            candidate_events = parser_service.parse_events(ocr_result["normalized_text"])
        except Exception as e:
            print(f"[PARSER WARN] Parsing fallback due to: {e}")
            candidate_events = []

        # Inject OCR warnings into events if OCR quality is poor
        if ocr_result.get("ocr_warnings"):
            for evt in candidate_events:
                for w in ocr_result["ocr_warnings"]:
                    evt["validation_flags"].append({
                        "type": "UNRELIABLE_OCR",
                        "severity": "warning",
                        "message": w
                    })

        # 4. Retrieve Existing Calendar Events for this session
        existing_events = []
        try:
            existing_events = calendar_service.get_calendar_events(session_id=session_id)
        except Exception as e:
            print(f"[WARN] Could not retrieve existing calendar events: {e}")

        # 5. Conflict & Duplicate Detection with Priority Advisory
        try:
            processed_events = conflict_advisor.inspect_conflicts_and_duplicates(
                candidate_events, existing_events
            )
        except Exception as e:
            print(f"[CONFLICT ADVISOR WARN] Conflict inspection fallback: {e}")
            processed_events = candidate_events

        # Track scan metrics
        try:
            conflict_count = sum(1 for e in processed_events if any(f.get("type") in ("SCHEDULE_CONFLICT", "DUPLICATE_EVENT") for f in e.get("validation_flags", [])))
            metrics_service.record_image_scan(
                event_count=len(processed_events),
                avg_confidence=ocr_result.get("avg_confidence", 0),
                conflicts=conflict_count
            )
        except Exception:
            pass

        return {
            "success": True,
            "filename": "screenshot.png",  # Safe sanitized display name
            "ocr": {
                "raw_text": ocr_result["raw_text"],
                "normalized_text": ocr_result["normalized_text"],
                "avg_confidence": ocr_result["avg_confidence"],
                "lines": ocr_result["lines"],
                "unreliable_lines": ocr_result["unreliable_lines"],
                "warnings": ocr_result["ocr_warnings"]
            },
            "events": processed_events,
            "existing_calendar_events": existing_events
        }
    except HTTPException:
        raise
    except Exception as exc:
        print(f"[IMAGE PROCESSING ERROR] {exc}")
        raise HTTPException(status_code=500, detail="Server image processing error.")
    finally:
        # Guaranteed cleanup of raw and sanitized image files
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)

@app.post("/api/validate-event")
def validate_event(request: Request, req: EventValidationRequest):
    """
    Re-validates an edited event against the calendar.
    Checks for cleared conflicts or newly introduced overlaps.
    """
    evt = req.event
    evt["validation_flags"] = [f for f in evt.get("validation_flags", []) if f.get("type") not in ("SCHEDULE_CONFLICT", "DUPLICATE_EVENT")]
    session_id = getattr(request.state, "session_id", None)
    
    existing_events = calendar_service.get_calendar_events(session_id=session_id)
    updated_events = conflict_advisor.inspect_conflicts_and_duplicates([evt], existing_events)
    return {"event": updated_events[0]}

@app.post("/api/calendar/submit")
def submit_events(request: Request, req: EventSubmissionRequest):
    """
    Finalizes confirmed events and pushes them to Google Calendar or Calendar Sandbox.
    """
    session_id = getattr(request.state, "session_id", None)
    results = []
    for evt in req.events:
        res = calendar_service.create_event(evt, session_id=session_id)
        results.append({
            "event_id": evt.get("id"),
            "title": evt.get("title"),
            "result": res
        })

    is_live_google = calendar_service.is_google_authenticated(session_id)
    
    # Record sync metrics
    try:
        metrics_service.record_calendar_sync(
            event_count=len(results),
            sync_type="google" if is_live_google else "sandbox"
        )
    except Exception:
        pass

    return {
        "success": True,
        "is_live_google": is_live_google,
        "processed_count": len(results),
        "results": results
    }

@app.post("/api/calendar/export-ics")
def export_ics(req: EventSubmissionRequest):
    """
    Generates downloadable RFC 5545-compliant .ics iCalendar file.
    """
    ics_content = calendar_service.generate_ics(req.events)
    return Response(
        content=ics_content,
        media_type="text/calendar",
        headers={"Content-Disposition": "attachment; filename=calendar_events.ics"}
    )

@app.get("/api/samples")
def list_samples():
    """Lists available sample screenshots for instant demonstration."""
    samples_dir = os.path.join(os.path.dirname(__file__), "..", "samples")
    if not os.path.exists(samples_dir):
        return {"samples": []}
    files = [f for f in os.listdir(samples_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    return {
        "samples": [
            {
                "id": f,
                "name": f.replace("_", " ").replace(".png", "").title(),
                "url": f"/samples/{f}"
            }
            for f in sorted(files)
        ]
    }

@app.get("/api/test-ocr")
def test_ocr_health():
    """Diagnostic check for Tesseract OCR binary and traineddata health."""
    import shutil
    import pytesseract
    from PIL import Image, ImageDraw
    
    tess_path = shutil.which("tesseract")
    ver = None
    langs = []
    engine_err = None
    try:
        ver = str(pytesseract.get_tesseract_version())
        langs = pytesseract.get_languages()
    except Exception as e:
        engine_err = str(e)
    
    # Quick test OCR execution
    test_text = None
    exec_err = None
    try:
        img = Image.new("RGB", (240, 60), color=(255, 255, 255))
        d = ImageDraw.Draw(img)
        d.text((10, 15), "CALENDAR OCR 2026", fill=(0, 0, 0))
        test_text = pytesseract.image_to_string(img).strip()
    except Exception as e:
        exec_err = str(e)

    return {
        "tesseract_cmd": pytesseract.pytesseract.tesseract_cmd,
        "tesseract_path": tess_path,
        "tessdata_prefix": os.environ.get("TESSDATA_PREFIX"),
        "version": ver,
        "languages": langs,
        "engine_error": engine_err,
        "sample_ocr_output": test_text,
        "sample_ocr_error": exec_err
    }

# ---------------------------------------------------------------------------
# 6. Legal & Admin Endpoints
# ---------------------------------------------------------------------------
@app.get("/privacy")
def serve_privacy_page():
    privacy_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "privacy.html")
    if os.path.exists(privacy_file):
        return FileResponse(privacy_file)
    raise HTTPException(status_code=404, detail="Privacy policy not found")

@app.get("/terms")
def serve_terms_page():
    terms_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "terms.html")
    if os.path.exists(terms_file):
        return FileResponse(terms_file)
    raise HTTPException(status_code=404, detail="Terms of service not found")

@app.get("/admin")
def serve_admin_page():
    admin_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "admin.html")
    if os.path.exists(admin_file):
        return FileResponse(admin_file)
    raise HTTPException(status_code=404, detail="Admin panel not found")

@app.get("/api/admin/metrics")
def get_creator_metrics(request: Request):
    client_ip = request.client.host if request.client else "unknown"
    
    # Rate limit admin verification attempts
    if not admin_limiter.is_allowed(client_ip, max_requests=5, window_seconds=60):
        raise HTTPException(status_code=429, detail="Too many admin login attempts. Please wait 60 seconds.")

    provided_pwd = request.headers.get("x-admin-password")
    
    if not verify_admin_password(provided_pwd, ADMIN_PASSWORD):
        raise HTTPException(status_code=401, detail="Invalid admin credentials.")
    
    return metrics_service.get_metrics_summary()

# ---------------------------------------------------------------------------
# 7. Static Directories Mount
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
samples_path = os.path.join(BASE_DIR, "samples")
frontend_path = os.path.join(BASE_DIR, "frontend")

if os.path.exists(samples_path):
    app.mount("/samples", StaticFiles(directory=samples_path), name="samples")

if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
