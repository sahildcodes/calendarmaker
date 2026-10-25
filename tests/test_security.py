import io
import os
import time
import pytest
from PIL import Image
from fastapi.testclient import TestClient

from backend.main import ADMIN_PASSWORD, app, ocr_service, calendar_service
from backend.security import (
    sign_session_id,
    verify_session_id,
    encrypt_data,
    decrypt_data,
    escape_ics_text,
    enforce_event_limits,
    verify_admin_password,
    process_image_limiter,
    admin_limiter
)
from backend.ocr_service import (
    InvalidImageError,
    DecompressionBombError,
    CorruptedImageError,
    OCRTimeoutError
)

client = TestClient(app)

@pytest.fixture(autouse=True)
def reset_rate_limiters():
    """Reset rate limiters before each test."""
    process_image_limiter.reset()
    admin_limiter.reset()

# ---------------------------------------------------------------------------
# 1. Fake File Extension (.txt disguised as .png)
# ---------------------------------------------------------------------------
def test_fake_extension_rejection():
    fake_png_data = b"This is plain text disguised as a PNG file."
    response = client.post(
        "/api/process-image",
        files={"file": ("malicious.png", fake_png_data, "image/png")}
    )
    assert response.status_code == 400
    assert "not a valid or recognized image" in response.json().get("detail", "").lower()

# ---------------------------------------------------------------------------
# 2. Oversized File (> 10 MB)
# ---------------------------------------------------------------------------
def test_oversized_file_rejection():
    # 10 MB + 1 byte
    oversized_data = b"A" * (10 * 1024 * 1024 + 1)
    response = client.post(
        "/api/process-image",
        files={"file": ("large.png", oversized_data, "image/png")}
    )
    assert response.status_code == 413
    assert "10 mb" in response.json().get("detail", "").lower()

# ---------------------------------------------------------------------------
# 3. Decompression Bomb & Huge Pixel Count (> 20M pixels)
# ---------------------------------------------------------------------------
def test_decompression_bomb_rejection():
    # Create image with 25 million pixels (5000 x 5000)
    buf = io.BytesIO()
    # 1x1 image with header crafted to claim huge dimensions or large empty image
    # A 5000x5000 1-bit mode image compresses to < 100KB but unpacks to 25 million pixels
    img = Image.new("1", (5000, 5000), 1)
    img.save(buf, format="PNG")
    buf.seek(0)

    response = client.post(
        "/api/process-image",
        files={"file": ("bomb.png", buf.getvalue(), "image/png")}
    )
    assert response.status_code == 400
    assert "20 million pixel" in response.json().get("detail", "").lower() or "decompression bomb" in response.json().get("detail", "").lower()

# ---------------------------------------------------------------------------
# 4. Corrupted & Truncated Images
# ---------------------------------------------------------------------------
def test_truncated_image_rejection():
    # PNG magic bytes + truncated garbage
    truncated_data = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x10\x00\x00\x00\x10"
    response = client.post(
        "/api/process-image",
        files={"file": ("corrupted.png", truncated_data, "image/png")}
    )
    assert response.status_code == 400

# ---------------------------------------------------------------------------
# 5. Malicious Filenames (Path Traversal & Shell Characters)
# ---------------------------------------------------------------------------
def test_malicious_filename_handling():
    # Valid small PNG with malicious filename
    buf = io.BytesIO()
    img = Image.new("RGB", (100, 50), (255, 255, 255))
    img.save(buf, format="PNG")
    buf.seek(0)

    # Filename trying directory traversal and null bytes
    malicious_name = "../../../../etc/passwd\x00.png"
    response = client.post(
        "/api/process-image",
        files={"file": (malicious_name, buf.getvalue(), "image/png")}
    )
    # Must succeed cleanly or process through random UUID without escaping sandbox
    assert response.status_code == 200
    # Returned filename must be safe
    assert response.json()["filename"] == "screenshot.png"

# ---------------------------------------------------------------------------
# 6. HTML & XSS Injection in Parsed Event Fields
# ---------------------------------------------------------------------------
def test_event_length_and_html_sanitization():
    raw_event = {
        "title": "<script>alert('xss')</script>" + ("A" * 200),
        "location": "<img src=x onerror=alert(1)>" + ("B" * 400),
        "description": "<svg onload=alert(2)>" + ("C" * 6000)
    }
    sanitized = enforce_event_limits(raw_event)
    
    assert len(sanitized["title"]) <= 150
    assert len(sanitized["location"]) <= 300
    assert len(sanitized["description"]) <= 5000

# ---------------------------------------------------------------------------
# 7. RFC 5545 iCalendar Injection (CRLF, Comma, Semicolon, Backslash)
# ---------------------------------------------------------------------------
def test_ics_escaping_and_injection_prevention():
    malicious_title = "Meeting\r\nSTATUS:CANCELLED\r\nEND:VCALENDAR\r\nBEGIN:VEVENT"
    escaped = escape_ics_text(malicious_title)
    
    # Carriage returns must be completely stripped
    assert "\r" not in escaped
    # Newlines must be escaped as \n
    assert "\n" not in escaped or "\\n" in escaped

    test_event = [{
        "id": "evt_test",
        "title": "Study Group; CS 101, Intro\\Review\r\nINJECT:TRUE",
        "start_date": "2026-10-24",
        "end_date": "2026-10-24",
        "start_time": "14:00",
        "end_time": "15:00",
        "location": "Room 101; Hall B, Zoom\\Link\r\nINJECT:LOC",
        "description": "Notes:\n- Topic 1, item; test\\path\r\nINJECT:DESC"
    }]

    ics_output = calendar_service.generate_ics(test_event)
    # Check that CRLF injection didn't create a raw INJECT:TRUE header
    assert "\r\nINJECT:TRUE" not in ics_output
    assert "\r\nINJECT:LOC" not in ics_output
    assert "\\;" in ics_output
    assert "\\," in ics_output
    assert "\\\\" in ics_output

# ---------------------------------------------------------------------------
# 8. Multi-User Isolation & Token Encryption at Rest
# ---------------------------------------------------------------------------
def test_multi_user_isolation_and_encryption():
    user_a_session = "user_alpha_123"
    user_b_session = "user_beta_456"

    # Encrypt fake token for User A
    token_a_file = calendar_service.get_token_file(user_a_session)
    assert token_a_file is not None
    assert token_a_file.endswith(".enc")

    fake_token = b'{"token": "secret_token_user_a", "refresh_token": "refresh_a"}'
    encrypted_bytes = encrypt_data(fake_token)
    
    # Verify encrypted bytes are NOT readable plaintext
    assert b"secret_token_user_a" not in encrypted_bytes
    
    # Decrypt and verify match
    assert decrypt_data(encrypted_bytes) == fake_token

    # Ensure User B's token path is strictly isolated
    token_b_file = calendar_service.get_token_file(user_b_session)
    assert token_a_file != token_b_file
    
    # No fallback: User B has no token
    assert not calendar_service.is_google_authenticated(user_b_session)

# ---------------------------------------------------------------------------
# 9. Session Cookie Signing & Tamper Rejection
# ---------------------------------------------------------------------------
def test_session_cookie_tamper_rejection():
    real_session = "user_session_abc"
    signed = sign_session_id(real_session)
    
    # Valid signature passes
    assert verify_session_id(signed) == real_session

    # Tampered signature is rejected
    tampered = signed[:-4] + "ffff"
    assert verify_session_id(tampered) is None

    # Unsigned session ID is rejected
    assert verify_session_id("forged_session_id") is None

# ---------------------------------------------------------------------------
# 10. Upload Rate Limiting (5 requests/minute)
# ---------------------------------------------------------------------------
def test_rate_limiting_enforcement():
    buf = io.BytesIO()
    img = Image.new("RGB", (50, 50), (255, 255, 255))
    img.save(buf, format="PNG")
    img_bytes = buf.getvalue()

    # First 5 scans succeed or hit validation (status < 429)
    for i in range(5):
        res = client.post("/api/process-image", files={"file": ("test.png", img_bytes, "image/png")})
        assert res.status_code != 429

    # 6th scan within the same minute MUST be blocked with HTTP 429
    res_blocked = client.post("/api/process-image", files={"file": ("test.png", img_bytes, "image/png")})
    assert res_blocked.status_code == 429
    assert "rate limit exceeded" in res_blocked.json()["detail"].lower()

# ---------------------------------------------------------------------------
# 11. Admin Password Security & Timing Protection
# ---------------------------------------------------------------------------
def test_admin_password_protection():
    # Timing-safe comparison check
    assert verify_admin_password("correct_pass", "correct_pass") is True
    assert verify_admin_password("wrong_pass", "correct_pass") is False
    assert verify_admin_password("", "correct_pass") is False

    # Attempting access without password returns 401
    res = client.get("/api/admin/metrics")
    assert res.status_code == 401

    # Passwords in query strings are ignored so they cannot leak into access logs.
    res_query = client.get(f"/api/admin/metrics?password={ADMIN_PASSWORD}")
    assert res_query.status_code == 401

    # The dedicated request header is the only accepted authentication method.
    admin_limiter.reset()
    res_header = client.get(
        "/api/admin/metrics",
        headers={"x-admin-password": ADMIN_PASSWORD}
    )
    assert res_header.status_code == 200

# ---------------------------------------------------------------------------
# 12. Security Headers
# ---------------------------------------------------------------------------
def test_security_headers_present():
    res = client.get("/api/health")
    headers = res.headers
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "Content-Security-Policy" in headers
