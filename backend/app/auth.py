import firebase_admin
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials

from .config import get_settings

_bearer_scheme = HTTPBearer(auto_error=False)


def _init_firebase_app() -> None:
    """Lazy init: only touches the service account file when a protected
    route is actually hit, so the app can boot without it present."""
    if not firebase_admin._apps:
        settings = get_settings()
        cred = credentials.Certificate(settings.firebase_service_account_path)
        firebase_admin.initialize_app(cred)


def get_current_uid(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> str:
    """Verifies the Firebase ID token server-side and returns the caller's uid.
    The uid NEVER comes from a client-supplied field — only from a verified token."""
    if creds is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    try:
        _init_firebase_app()
    except Exception as exc:
        # Missing/malformed service-account file — a server misconfiguration, not a bad
        # token, so it gets its own status code rather than masquerading as a 401.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is not configured correctly",
        ) from exc

    try:
        decoded = firebase_auth.verify_id_token(creds.credentials)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        ) from exc

    uid = decoded.get("uid")
    if not uid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing uid claim")
    return uid
