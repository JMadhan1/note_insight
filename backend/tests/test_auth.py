from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.auth import get_current_uid


def test_missing_token_returns_401():
    with pytest.raises(HTTPException) as exc_info:
        get_current_uid(creds=None)
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Missing bearer token"


@patch("app.auth._init_firebase_app")
def test_firebase_init_failure_returns_503_not_500(mock_init):
    """A missing/malformed service-account file (e.g. a Secret File that wasn't
    uploaded on the deploy host) is a server misconfiguration, not a bad token —
    it must surface as a clean 503, never as an unhandled 500."""
    mock_init.side_effect = FileNotFoundError("serviceAccountKey.json not found")
    creds = MagicMock()
    creds.credentials = "irrelevant"

    with pytest.raises(HTTPException) as exc_info:
        get_current_uid(creds=creds)

    assert exc_info.value.status_code == 503


@patch("app.auth.firebase_auth")
@patch("app.auth._init_firebase_app")
def test_invalid_token_returns_401(mock_init, mock_firebase_auth):
    mock_init.return_value = None
    mock_firebase_auth.verify_id_token.side_effect = ValueError("bad token")
    creds = MagicMock()
    creds.credentials = "garbage"

    with pytest.raises(HTTPException) as exc_info:
        get_current_uid(creds=creds)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid or expired token"


@patch("app.auth.firebase_auth")
@patch("app.auth._init_firebase_app")
def test_valid_token_returns_uid(mock_init, mock_firebase_auth):
    mock_init.return_value = None
    mock_firebase_auth.verify_id_token.return_value = {"uid": "user-123"}
    creds = MagicMock()
    creds.credentials = "valid-token"

    uid = get_current_uid(creds=creds)

    assert uid == "user-123"


@patch("app.auth.firebase_auth")
@patch("app.auth._init_firebase_app")
def test_token_missing_uid_claim_returns_401(mock_init, mock_firebase_auth):
    mock_init.return_value = None
    mock_firebase_auth.verify_id_token.return_value = {"email": "no-uid@example.com"}
    creds = MagicMock()
    creds.credentials = "weird-token"

    with pytest.raises(HTTPException) as exc_info:
        get_current_uid(creds=creds)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Token missing uid claim"
