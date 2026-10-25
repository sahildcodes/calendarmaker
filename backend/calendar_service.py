import os
import json
import threading
from datetime import datetime, date, timedelta, timezone
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse

try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import Flow
    from googleapiclient.discovery import build
    GOOGLE_LIBS_AVAILABLE = True
except ImportError:
    GOOGLE_LIBS_AVAILABLE = False

from backend.security import (
    encrypt_data,
    decrypt_data,
    escape_ics_text,
    enforce_event_limits
)

# Minimum Scopes: calendar events + user email profile
SCOPES = [
    'https://www.googleapis.com/auth/calendar.events',
    'https://www.googleapis.com/auth/userinfo.email',
    'openid'
]

class CalendarService:
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self.tokens_dir = os.path.join(data_dir, "tokens")
        self.profiles_dir = os.path.join(data_dir, "profiles")
        self.runtime_dir = os.path.join(data_dir, "runtime")
        os.makedirs(self.tokens_dir, exist_ok=True)
        os.makedirs(self.profiles_dir, exist_ok=True)
        os.makedirs(self.runtime_dir, exist_ok=True)
        self.credentials_file = os.path.join(data_dir, "credentials.json")
        self.sandbox_template_file = os.path.join(data_dir, "sandbox_calendar.json")
        self.sandbox_events_file = os.path.join(self.runtime_dir, "sandbox_calendar.json")
        self._lock = threading.RLock()
        for private_dir in (self.tokens_dir, self.profiles_dir, self.runtime_dir):
            try:
                os.chmod(private_dir, 0o700)
            except OSError:
                pass
        self._init_sandbox_events()

    def get_token_file(self, session_id: Optional[str] = None) -> Optional[str]:
        """
        Returns session-specific token file path for multi-user isolation.
        No shared token fallback: sessions strictly access only their own encrypted credentials.
        """
        if not session_id:
            return None
        safe_id = "".join(c for c in session_id if c.isalnum() or c in "-_")
        if not safe_id:
            return None
        return os.path.join(self.tokens_dir, f"{safe_id}.enc")

    def get_user_profile_file(self, session_id: Optional[str] = None) -> Optional[str]:
        """Returns session-specific user profile file path."""
        if not session_id:
            return None
        safe_id = "".join(c for c in session_id if c.isalnum() or c in "-_")
        if not safe_id:
            return None
        return os.path.join(self.profiles_dir, f"{safe_id}.enc")

    def _init_sandbox_events(self):
        """Initializes default realistic sandbox calendar events for conflict & duplicate demos."""
        with self._lock:
            if not os.path.exists(self.sandbox_events_file):
                default_events = None
                if os.path.exists(self.sandbox_template_file):
                    try:
                        with open(self.sandbox_template_file, "r", encoding="utf-8") as f:
                            default_events = json.load(f)
                    except (OSError, ValueError):
                        default_events = None
                if default_events is None:
                    default_events = [
                    {
                        "id": "cal_evt_1",
                        "title": "CS 101 Midterm Examination",
                        "start_date": "2026-10-24",
                        "end_date": "2026-10-24",
                        "start_time": "14:00",
                        "end_time": "16:00",
                        "category": "Exam",
                        "priority_score": 9,
                        "location": "Science Center Hall B",
                        "description": "Comprehensive Midterm covering dynamic programming, graph algorithms, and trees."
                    },
                    {
                        "id": "cal_evt_2",
                        "title": "Weekly Board Game Social",
                        "start_date": "2026-10-24",
                        "end_date": "2026-10-24",
                        "start_time": "15:00",
                        "end_time": "17:00",
                        "category": "Social",
                        "priority_score": 3,
                        "location": "Student Union 2nd Floor",
                        "description": "Casual board game night with friends."
                    },
                    {
                        "id": "cal_evt_3",
                        "title": "CS 101 Homework 4: Dynamic Programming",
                        "start_date": "2026-10-24",
                        "end_date": "2026-10-24",
                        "start_time": "23:59",
                        "end_time": "23:59",
                        "category": "Assignment",
                        "priority_score": 8,
                        "location": "Canvas Submission Portal",
                        "description": "Submit homework zip to Canvas before midnight."
                    },
                    {
                        "id": "cal_evt_4",
                        "title": "Campus Hackathon 2026",
                        "start_date": "2026-11-14",
                        "end_date": "2026-11-14",
                        "start_time": "18:00",
                        "end_time": "21:30",
                        "category": "Event",
                        "priority_score": 6,
                        "location": "Student Union Grand Ballroom",
                        "description": "Hackathon opening keynote and team matchmaking."
                    },
                    {
                        "id": "cal_evt_5",
                        "title": "Campus Recreation Shift",
                        "start_date": "2026-11-14",
                        "end_date": "2026-11-14",
                        "start_time": "19:00",
                        "end_time": "22:00",
                        "category": "Work",
                        "priority_score": 7,
                        "location": "Fitness Center Desk",
                        "description": "Work shift - equipment monitoring."
                    }
                ]
                with open(self.sandbox_events_file, "w", encoding="utf-8") as f:
                    json.dump(default_events, f, indent=2)
                os.chmod(self.sandbox_events_file, 0o600)

    def get_credentials_path(self) -> Optional[str]:
        """
        Auto-discovers Google OAuth credentials from:
        1. Project root credentials.json
        2. Environment variable GOOGLE_CREDENTIALS_JSON
        3. Environment variables GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET
        """
        import glob
        try:
            import dotenv
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            dotenv.load_dotenv(os.path.join(project_root, ".env"))
        except Exception:
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # 1. Project root credentials.json
        root_creds = os.path.join(project_root, "credentials.json")
        if os.path.exists(root_creds) and self._is_valid_credentials_file(root_creds):
            return root_creds

        # 2. Any client_secret*.json in root
        root_matches = glob.glob(os.path.join(project_root, "client_secret*.json"))
        for m in root_matches:
            if self._is_valid_credentials_file(m):
                return m

        # 3. data/credentials.json
        if os.path.exists(self.credentials_file) and self._is_valid_credentials_file(self.credentials_file):
            return self.credentials_file

        # 4. Environment variable GOOGLE_CREDENTIALS_JSON
        creds_json_str = os.environ.get("GOOGLE_CREDENTIALS_JSON", "").strip()
        if creds_json_str:
            try:
                parsed = json.loads(creds_json_str)
                with open(self.credentials_file, "w", encoding="utf-8") as f:
                    json.dump(parsed, f, indent=2)
                os.chmod(self.credentials_file, 0o600)
                if self._is_valid_credentials_file(self.credentials_file):
                    return self.credentials_file
            except Exception:
                pass

        # 5. Environment variables GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET
        client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
        client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
        if client_id and client_secret and "apps.googleusercontent.com" in client_id and client_id != "test-client-id.apps.googleusercontent.com":
            self.save_client_config(client_id, client_secret)
            return self.credentials_file

        return None

    def _is_valid_credentials_file(self, filepath: str) -> bool:
        """Validates that credentials JSON has real web or installed client credentials."""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            client_dict = data.get("web") or data.get("installed")
            if not client_dict:
                return False
            client_id = client_dict.get("client_id", "")
            client_secret = client_dict.get("client_secret", "")
            return bool(
                client_id and client_secret and
                "apps.googleusercontent.com" in client_id and
                client_id != "test-client-id.apps.googleusercontent.com"
            )
        except Exception:
            return False

    def has_client_credentials(self) -> bool:
        """Checks if valid Google OAuth client credentials exist."""
        return self.get_credentials_path() is not None

    def get_credentials_source(self) -> Optional[str]:
        """Returns the source where credentials were found."""
        p = self.get_credentials_path()
        if p:
            return os.path.basename(p)
        return None

    def save_client_config(self, client_id: str, client_secret: str, redirect_uri: Optional[str] = None) -> bool:
        """Saves Google OAuth Client configuration."""
        config = {
            "web": {
                "client_id": client_id.strip(),
                "client_secret": client_secret.strip(),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs"
            }
        }
        if redirect_uri:
            config["web"]["redirect_uris"] = [redirect_uri.strip()]
        with self._lock:
            with open(self.credentials_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
            os.chmod(self.credentials_file, 0o600)
        return True

    @staticmethod
    def _configure_oauth_transport(redirect_uri: str) -> None:
        """Allow plain HTTP only for local OAuth development callbacks."""
        parsed = urlparse(redirect_uri)
        is_local_http = parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}
        if is_local_http:
            os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
        else:
            os.environ.pop("OAUTHLIB_INSECURE_TRANSPORT", None)

    def get_auth_url(self, redirect_uri: str) -> Dict[str, Any]:
        """Generates Google OAuth 2.0 consent authorization URL."""
        cred_path = self.get_credentials_path()
        if not cred_path:
            raise ValueError("Google OAuth credentials have not been configured on the server.")

        self._configure_oauth_transport(redirect_uri)
        os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

        flow = Flow.from_client_secrets_file(
            cred_path,
            scopes=SCOPES,
            redirect_uri=redirect_uri
        )
        auth_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )
        if flow.code_verifier:
            with self._lock:
                if not hasattr(self, "_oauth_states"):
                    self._oauth_states = {}
                self._oauth_states[state] = flow.code_verifier
        return {"auth_url": auth_url, "state": state}

    def handle_oauth_callback(self, code: str, redirect_uri: str, session_id: Optional[str] = None, state: Optional[str] = None) -> Dict[str, Any]:
        """Exchanges auth code for tokens and encrypts credentials for this session."""
        if not session_id:
            raise ValueError("Invalid or missing session identifier.")

        cred_path = self.get_credentials_path()
        if not cred_path:
            raise ValueError("Google OAuth credentials file missing during callback.")

        self._configure_oauth_transport(redirect_uri)
        os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

        flow = Flow.from_client_secrets_file(
            cred_path,
            scopes=SCOPES,
            redirect_uri=redirect_uri,
            state=state
        )
        
        # Restore PKCE code verifier if state was tracked
        verifier = None
        if state and hasattr(self, "_oauth_states"):
            with self._lock:
                verifier = self._oauth_states.pop(state, None)
        
        if verifier:
            flow.code_verifier = verifier
        else:
            flow.autogenerate_code_verifier = False

        flow.fetch_token(code=code)
        creds = flow.credentials

        target_token_file = self.get_token_file(session_id)
        if not target_token_file:
            raise ValueError("Cannot resolve secure token path for session.")

        # Save encrypted token
        token_bytes = creds.to_json().encode("utf-8")
        encrypted_token = encrypt_data(token_bytes)
        with self._lock:
            with open(target_token_file, "wb") as f:
                f.write(encrypted_token)
            os.chmod(target_token_file, 0o600)

        # Retrieve user email and save encrypted profile
        email = "Google User"
        try:
            oauth2_service = build('oauth2', 'v2', credentials=creds)
            user_info = oauth2_service.userinfo().get().execute()
            email = user_info.get("email", email)
            target_profile_file = self.get_user_profile_file(session_id)
            if target_profile_file:
                profile_bytes = json.dumps({"email": email, "name": user_info.get("name", "")}).encode("utf-8")
                encrypted_profile = encrypt_data(profile_bytes)
                with self._lock:
                    with open(target_profile_file, "wb") as f:
                        f.write(encrypted_profile)
                    os.chmod(target_profile_file, 0o600)
        except Exception:
            pass

        return {"success": True, "email": email}

    def _load_credentials(self, session_id: Optional[str]) -> Optional[Credentials]:
        """Loads and decrypts Google OAuth credentials for a specific session."""
        token_f = self.get_token_file(session_id)
        if not token_f or not os.path.exists(token_f) or not GOOGLE_LIBS_AVAILABLE:
            return None

        try:
            with open(token_f, "rb") as f:
                ciphertext = f.read()
            decrypted = decrypt_data(ciphertext).decode("utf-8")
            token_info = json.loads(decrypted)
            creds = Credentials.from_authorized_user_info(token_info, SCOPES)
            return creds
        except Exception:
            # If token is corrupted or key changed, clean up securely
            try:
                if os.path.exists(token_f):
                    os.remove(token_f)
            except Exception:
                pass
            return None

    def disconnect_google(self, session_id: Optional[str] = None) -> bool:
        """
        Revokes Google OAuth access with Google's revocation endpoint
        and removes local encrypted tokens and profiles for this session.
        """
        token_f = self.get_token_file(session_id)
        profile_f = self.get_user_profile_file(session_id)

        # 1. Attempt online token revocation with Google
        if token_f and os.path.exists(token_f):
            try:
                with open(token_f, "rb") as f:
                    ciphertext = f.read()
                decrypted = decrypt_data(ciphertext).decode("utf-8")
                token_data = json.loads(decrypted)
                revocation_token = token_data.get("token") or token_data.get("refresh_token")
                if revocation_token:
                    import requests
                    requests.post(
                        "https://oauth2.googleapis.com/revoke",
                        data={"token": revocation_token},
                        headers={"content-type": "application/x-www-form-urlencoded"},
                        timeout=5
                    )
            except Exception:
                pass

        # 2. Delete local encrypted credentials
        with self._lock:
            if token_f and os.path.exists(token_f):
                try:
                    os.remove(token_f)
                except Exception:
                    pass
            if profile_f and os.path.exists(profile_f):
                try:
                    os.remove(profile_f)
                except Exception:
                    pass
        return True

    def get_user_profile(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Returns connected user email if authenticated for this session."""
        if not self.is_google_authenticated(session_id):
            return {"authenticated": False, "email": None}
        profile_f = self.get_user_profile_file(session_id)
        if profile_f and os.path.exists(profile_f):
            try:
                with open(profile_f, "rb") as f:
                    decrypted = decrypt_data(f.read()).decode("utf-8")
                return json.load(decrypted)
            except Exception:
                pass
        return {"authenticated": True, "email": "Google Calendar User"}

    def is_google_authenticated(self, session_id: Optional[str] = None) -> bool:
        """Checks if Google OAuth tokens are saved, valid, and decryptable for this session."""
        creds = self._load_credentials(session_id)
        return creds is not None and (creds.valid or creds.refresh_token is not None)

    def get_calendar_events(self, start_date: Optional[str] = None, end_date: Optional[str] = None, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retrieves calendar events. Uses Google Calendar API if authenticated for this session,
        otherwise returns events from the live Sandbox Calendar.
        """
        if self.is_google_authenticated(session_id):
            try:
                creds = self._load_credentials(session_id)
                if creds and creds.expired and creds.refresh_token:
                    from google.auth.transport.requests import Request
                    creds.refresh(Request())
                    token_f = self.get_token_file(session_id)
                    if token_f:
                        with self._lock:
                            with open(token_f, "wb") as f:
                                f.write(encrypt_data(creds.to_json().encode("utf-8")))

                service = build('calendar', 'v3', credentials=creds)
                
                # Fetch calendar events within window
                now = datetime.now(timezone.utc)
                time_min = (datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc) if start_date else (now - timedelta(days=7))).isoformat()
                time_max = (datetime.fromisoformat(end_date).replace(tzinfo=timezone.utc) if end_date else (now + timedelta(days=90))).isoformat()

                events_result = service.events().list(
                    calendarId='primary',
                    timeMin=time_min,
                    timeMax=time_max,
                    maxResults=50,
                    singleEvents=True,
                    orderBy='startTime'
                ).execute()
                items = events_result.get('items', [])

                formatted_events = []
                for item in items:
                    start = item.get('start', {})
                    end = item.get('end', {})
                    s_dt_str = start.get('dateTime', start.get('date', ''))
                    e_dt_str = end.get('dateTime', end.get('date', ''))

                    s_date, s_time = "", ""
                    if 'T' in s_dt_str:
                        parts = s_dt_str.split('T')
                        s_date = parts[0]
                        s_time = parts[1][:5]
                    else:
                        s_date = s_dt_str

                    formatted_events.append({
                        "id": item.get('id'),
                        "title": item.get('summary', 'Untitled Event'),
                        "start_date": s_date,
                        "end_date": e_dt_str.split('T')[0] if 'T' in e_dt_str else e_dt_str,
                        "start_time": s_time,
                        "end_time": e_dt_str.split('T')[1][:5] if 'T' in e_dt_str else "",
                        "location": item.get('location', ''),
                        "description": item.get('description', ''),
                        "html_link": item.get('htmlLink', ''),
                        "category": "Google Calendar",
                        "priority_score": 6
                    })
                return formatted_events
            except Exception as e:
                print(f"Error fetching from Google Calendar: {e}")

        # Fallback to Sandbox events
        with self._lock:
            if not os.path.exists(self.sandbox_events_file):
                self._init_sandbox_events()
            try:
                with open(self.sandbox_events_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []

    def create_event(self, event_data: Dict[str, Any], session_id: Optional[str] = None) -> Dict[str, Any]:
        """Creates an event on Google Calendar if authenticated, or in the Sandbox calendar."""
        event_data = enforce_event_limits(event_data)

        if self.is_google_authenticated(session_id):
            try:
                creds = self._load_credentials(session_id)
                if creds and creds.expired and creds.refresh_token:
                    from google.auth.transport.requests import Request
                    creds.refresh(Request())
                    token_f = self.get_token_file(session_id)
                    if token_f:
                        with self._lock:
                            with open(token_f, "wb") as f:
                                f.write(encrypt_data(creds.to_json().encode("utf-8")))

                service = build('calendar', 'v3', credentials=creds)

                s_date = event_data.get("start_date")
                s_time = event_data.get("start_time")
                e_date = event_data.get("end_date", s_date)
                e_time = event_data.get("end_time")

                if s_time:
                    start_body = {"dateTime": f"{s_date}T{s_time}:00", "timeZone": "UTC"}
                else:
                    start_body = {"date": s_date}

                if e_time:
                    end_body = {"dateTime": f"{e_date}T{e_time}:00", "timeZone": "UTC"}
                else:
                    end_body = {"date": e_date or s_date}

                event_body: Dict[str, Any] = {
                    'summary': event_data.get("title"),
                    'location': event_data.get("location", ""),
                    'description': event_data.get("description", ""),
                    'start': start_body,
                    'end': end_body,
                }

                if event_data.get("recurrence"):
                    event_body['recurrence'] = [event_data.get("recurrence")]

                created = service.events().insert(calendarId='primary', body=event_body).execute()
                return {
                    "success": True,
                    "mode": "google_calendar",
                    "event_id": created.get("id"),
                    "html_link": created.get("htmlLink"),
                    "message": f"Successfully created event on Google Calendar: {event_data.get('title')}"
                }
            except Exception as e:
                return {
                    "success": False,
                    "mode": "google_calendar",
                    "error": str(e),
                    "message": f"Google Calendar API submission failed: {e}"
                }

        # Sandbox insertion
        with self._lock:
            with open(self.sandbox_events_file, "r", encoding="utf-8") as f:
                events = json.load(f)
            
            new_id = f"sandbox_{int(datetime.now().timestamp())}_{len(events)+1}"
            new_entry = {
                "id": new_id,
                "title": event_data.get("title"),
                "start_date": event_data.get("start_date"),
                "end_date": event_data.get("end_date", event_data.get("start_date")),
                "start_time": event_data.get("start_time"),
                "end_time": event_data.get("end_time"),
                "location": event_data.get("location", ""),
                "description": event_data.get("description", ""),
                "category": event_data.get("category", "Event"),
                "priority_score": event_data.get("priority_score", 5),
                "html_link": "#sandbox"
            }
            events.append(new_entry)
            with open(self.sandbox_events_file, "w", encoding="utf-8") as f:
                json.dump(events, f, indent=2)
            os.chmod(self.sandbox_events_file, 0o600)

        return {
            "success": True,
            "mode": "sandbox",
            "event_id": new_id,
            "html_link": "#sandbox",
            "message": f"Event '{event_data.get('title')}' successfully verified and saved to Calendar Sandbox!"
        }

    def generate_ics(self, events: List[Dict[str, Any]]) -> str:
        """
        Generates RFC 5545-compliant iCalendar (.ics) string with strict escaping
        preventing header injection or malformed calendar boundaries.
        """
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Image-to-Calendar Application//EN",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH"
        ]

        now_str = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

        for evt in events:
            evt = enforce_event_limits(evt)
            s_date = evt.get("start_date", "").replace("-", "")
            s_time = evt.get("start_time", "09:00").replace(":", "") + "00"
            e_date = evt.get("end_date", evt.get("start_date", "")).replace("-", "")
            e_time = evt.get("end_time", "10:00").replace(":", "") + "00"

            uid = f"{evt.get('id', 'evt')}_{s_date}T{s_time}@imagetocalendar.app"
            title = escape_ics_text(evt.get("title", "Event"))
            desc = escape_ics_text(evt.get("description", ""))
            loc = escape_ics_text(evt.get("location", ""))

            lines.append("BEGIN:VEVENT")
            lines.append(f"UID:{uid}")
            lines.append(f"DTSTAMP:{now_str}")
            lines.append(f"DTSTART:{s_date}T{s_time}")
            lines.append(f"DTEND:{e_date}T{e_time}")
            lines.append(f"SUMMARY:{title}")
            if loc:
                lines.append(f"LOCATION:{loc}")
            if desc:
                lines.append(f"DESCRIPTION:{desc}")
            if evt.get("category"):
                lines.append(f"CATEGORIES:{escape_ics_text(evt.get('category').upper())}")
            lines.append("STATUS:CONFIRMED")
            lines.append("END:VEVENT")

        lines.append("END:VCALENDAR")
        return "\r\n".join(lines)
