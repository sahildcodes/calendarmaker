import os
import hmac
import hashlib
import base64
import time
import secrets
import threading
from typing import Optional, Dict, List, Any
from cryptography.fernet import Fernet, InvalidToken

# Data directory path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# 1. Master Secret & Key Derivation
# ---------------------------------------------------------------------------
def _get_master_secret() -> str:
    """Retrieves or creates a persistent master secret key for signing & encryption."""
    env_secret = (os.environ.get("SESSION_SECRET_KEY", "") or os.environ.get("SESSION_SECRET", "")).strip()
    if env_secret:
        return env_secret

    secret_file = os.path.join(DATA_DIR, ".secret_key")
    if os.path.exists(secret_file):
        try:
            with open(secret_file, "r", encoding="utf-8") as f:
                secret = f.read().strip()
                if len(secret) >= 32:
                    return secret
        except Exception:
            pass

    # Generate a strong 32-byte (64 hex chars) persistent secret
    new_secret = secrets.token_hex(32)
    try:
        with open(secret_file, "w", encoding="utf-8") as f:
            f.write(new_secret)
        # Restrict permissions on secret file to user-only (0600)
        os.chmod(secret_file, 0o600)
    except Exception:
        pass
    return new_secret

MASTER_SECRET = _get_master_secret()

# ---------------------------------------------------------------------------
# 2. Session ID Signing & Verification (HMAC-SHA256)
# ---------------------------------------------------------------------------
def sign_session_id(session_id: str) -> str:
    """Signs a session ID using HMAC-SHA256."""
    sig = hmac.new(MASTER_SECRET.encode("utf-8"), session_id.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{session_id}.{sig}"

def verify_session_id(signed_value: Optional[str]) -> Optional[str]:
    """
    Verifies the HMAC signature on a session cookie.
    Returns the raw session ID if valid, or None if tampered or missing.
    """
    if not signed_value or "." not in signed_value:
        return None
    parts = signed_value.rsplit(".", 1)
    if len(parts) != 2:
        return None
    session_id, sig = parts
    expected_sig = hmac.new(MASTER_SECRET.encode("utf-8"), session_id.encode("utf-8"), hashlib.sha256).hexdigest()
    if hmac.compare_digest(sig, expected_sig):
        return session_id
    return None

# ---------------------------------------------------------------------------
# 3. Token Encryption at Rest (Fernet AES-128-CBC + HMAC)
# ---------------------------------------------------------------------------
def _get_fernet_cipher() -> Fernet:
    """Derives a url-safe base64 32-byte Fernet key from the master secret."""
    key = base64.urlsafe_b64encode(hashlib.sha256(MASTER_SECRET.encode("utf-8")).digest())
    return Fernet(key)

_CIPHER = _get_fernet_cipher()

def encrypt_data(data: bytes) -> bytes:
    """Encrypts bytes using Fernet."""
    return _CIPHER.encrypt(data)

def decrypt_data(token_bytes: bytes) -> bytes:
    """Decrypts bytes using Fernet. Raises InvalidToken on tampering or corruption."""
    return _CIPHER.decrypt(token_bytes)

# ---------------------------------------------------------------------------
# 4. Thread-Safe Sliding Window Rate Limiter
# ---------------------------------------------------------------------------
class RateLimiter:
    """In-memory sliding window rate limiter."""
    def __init__(self):
        self._history: Dict[str, List[float]] = {}
        self._lock = threading.Lock()

    def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> bool:
        """
        Returns True if the request within the window is allowed, False if exceeded.
        """
        now = time.time()
        with self._lock:
            if key not in self._history:
                self._history[key] = []
            
            # Filter out timestamps outside the sliding window
            cutoff = now - window_seconds
            self._history[key] = [t for t in self._history[key] if t > cutoff]

            if len(self._history[key]) >= max_requests:
                return False

            self._history[key].append(now)
            return True

    def reset(self, key: Optional[str] = None):
        """Clears rate limit history for testing."""
        with self._lock:
            if key:
                self._history.pop(key, None)
            else:
                self._history.clear()

# Global instances
process_image_limiter = RateLimiter()  # 5 requests / 60 seconds
admin_limiter = RateLimiter()          # 5 requests / 60 seconds

# ---------------------------------------------------------------------------
# 5. Length Bounding & Content Sanitization
# ---------------------------------------------------------------------------
MAX_TITLE_LENGTH = 150
MAX_LOCATION_LENGTH = 300
MAX_DESCRIPTION_LENGTH = 5000
MAX_OCR_TEXT_LENGTH = 100000

def sanitize_text(text: Optional[str], max_len: int) -> str:
    """Strips control characters, normalizes whitespace, and truncates to max_len."""
    if not text:
        return ""
    # Remove NULL bytes and non-printable control characters (except newline, tab)
    cleaned = "".join(ch for ch in text if ch in ("\n", "\t", "\r") or (ord(ch) >= 32))
    return cleaned[:max_len]

def enforce_event_limits(event: Dict[str, Any]) -> Dict[str, Any]:
    """Enforces strict length bounds on all event text fields."""
    event["title"] = sanitize_text(event.get("title", ""), MAX_TITLE_LENGTH)
    event["location"] = sanitize_text(event.get("location", ""), MAX_LOCATION_LENGTH)
    event["description"] = sanitize_text(event.get("description", ""), MAX_DESCRIPTION_LENGTH)
    return event

# ---------------------------------------------------------------------------
# 6. RFC 5545 iCalendar Escaping
# ---------------------------------------------------------------------------
def escape_ics_text(text: Optional[str]) -> str:
    """
    Escapes text according to RFC 5545 specifications:
    - Backslash \ -> \\
    - Semicolon ; -> \;
    - Comma , -> \,
    - Newlines -> \\n
    - Strips carriage returns to prevent CRLF injection of arbitrary calendar properties.
    """
    if not text:
        return ""
    # Strip carriage returns first to prevent header injection
    cleaned = text.replace("\r", "")
    # Escape backslash first so subsequent escapes aren't double-escaped
    cleaned = cleaned.replace("\\", "\\\\")
    cleaned = cleaned.replace(";", "\\;")
    cleaned = cleaned.replace(",", "\\,")
    cleaned = cleaned.replace("\n", "\\n")
    return cleaned

# ---------------------------------------------------------------------------
# 7. Constant-Time Admin Authentication
# ---------------------------------------------------------------------------
def verify_admin_password(provided: Optional[str], expected: Optional[str]) -> bool:
    """Compares passwords using constant-time comparison to prevent timing attacks."""
    if not provided or not expected:
        return False
    return secrets.compare_digest(provided.strip(), expected.strip())
