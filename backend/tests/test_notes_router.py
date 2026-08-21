"""Integration tests at the HTTP layer: real FastAPI routing and response
validation, with the Firebase token check swapped out via dependency_override
(so these don't need live Firebase) and the Firestore/Gemini calls mocked.
Covers the failure-path and cross-user-access requirements explicitly called
out in the assessment's evaluation criteria.
"""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.auth import get_current_uid
from app.gemini_service import AnalysisFailure
from app.main import app
from app.models import (
    AnalysisResponse,
    AnalysisStatus,
    NoteResponse,
    ReviewStatus,
    StoredAnalysisOutput,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def _as_uid(uid: str) -> None:
    app.dependency_overrides[get_current_uid] = lambda: uid


def _sample_note(uid_suffix: str = "1") -> NoteResponse:
    return NoteResponse(
        id=f"note-{uid_suffix}",
        note_text="Patient has hypertension.",
        pseudonym=None,
        visit_date=None,
        created_at="2026-01-01T00:00:00Z",
        latest_analysis_id=f"analysis-{uid_suffix}",
    )


def _sample_analysis(status: AnalysisStatus, note_id: str = "note-1") -> AnalysisResponse:
    return AnalysisResponse(
        id="analysis-1",
        note_id=note_id,
        created_at="2026-01-01T00:00:00Z",
        model_version="gemini-2.5-flash",
        prompt_version="v1",
        status=status,
        ai_output=StoredAnalysisOutput(conditions=[], documentation_gaps=[], summary="ok")
        if status == AnalysisStatus.COMPLETE
        else None,
        review=None,
        review_status=ReviewStatus.PENDING,
        error_message=None if status != AnalysisStatus.FAILED else "boom",
    )


def test_submit_note_requires_auth():
    response = client.post("/notes", json={"note_text": "Patient has a cold."})
    assert response.status_code == 401


def test_submit_note_success(monkeypatch):
    _as_uid("uid-1")
    note = _sample_note()
    analysis = _sample_analysis(AnalysisStatus.COMPLETE)

    monkeypatch.setattr("app.routers.notes.db.create_note", MagicMock(return_value=note))
    monkeypatch.setattr("app.routers.notes.db.create_analysis_pending", MagicMock(return_value="analysis-1"))
    monkeypatch.setattr(
        "app.routers.notes.run_analysis",
        MagicMock(return_value=(StoredAnalysisOutput(conditions=[], documentation_gaps=[], summary="ok"), "gemini-2.5-flash")),
    )
    monkeypatch.setattr("app.routers.notes.db.complete_analysis", MagicMock())
    monkeypatch.setattr("app.routers.notes.db.get_note", MagicMock(return_value=note))
    monkeypatch.setattr("app.routers.notes.db.get_analysis", MagicMock(return_value=analysis))

    response = client.post("/notes", json={"note_text": "Patient has hypertension."})

    assert response.status_code == 201
    body = response.json()
    assert body["analysis"]["status"] == "complete"


def test_submit_note_stores_failed_analysis_instead_of_500(monkeypatch):
    """The model failing to produce valid output must not crash the request or
    lose the note — it must be recorded as a failed analysis."""
    _as_uid("uid-1")
    note = _sample_note()
    failed_analysis = _sample_analysis(AnalysisStatus.FAILED)

    monkeypatch.setattr("app.routers.notes.db.create_note", MagicMock(return_value=note))
    monkeypatch.setattr("app.routers.notes.db.create_analysis_pending", MagicMock(return_value="analysis-1"))
    monkeypatch.setattr(
        "app.routers.notes.run_analysis",
        MagicMock(side_effect=AnalysisFailure("model returned garbage twice")),
    )
    fail_analysis_mock = MagicMock()
    monkeypatch.setattr("app.routers.notes.db.fail_analysis", fail_analysis_mock)
    monkeypatch.setattr("app.routers.notes.db.get_note", MagicMock(return_value=note))
    monkeypatch.setattr("app.routers.notes.db.get_analysis", MagicMock(return_value=failed_analysis))

    response = client.post("/notes", json={"note_text": "Patient has hypertension."})

    assert response.status_code == 201  # note itself was still created successfully
    assert response.json()["analysis"]["status"] == "failed"
    fail_analysis_mock.assert_called_once()


def test_submit_note_rejects_blank_text():
    _as_uid("uid-1")
    response = client.post("/notes", json={"note_text": "   "})
    assert response.status_code == 422


def test_submit_note_rejects_oversized_text():
    _as_uid("uid-1")
    response = client.post("/notes", json={"note_text": "a" * 60001})
    assert response.status_code == 422


def test_get_note_not_found_returns_404(monkeypatch):
    _as_uid("uid-1")
    monkeypatch.setattr("app.routers.notes.db.get_note", MagicMock(return_value=None))

    response = client.get("/notes/does-not-exist")

    assert response.status_code == 404


def test_cross_user_note_access_returns_404_not_data(monkeypatch):
    """Simulates user B guessing user A's note id. Because firestore_service.get_note
    always looks under users/{calling_uid}/notes/{note_id} (see
    test_firestore_isolation.py), a note that doesn't exist under the caller's own
    uid returns None — the router must turn that into 404, never into someone
    else's data."""
    _as_uid("user-b")
    get_note_mock = MagicMock(return_value=None)
    monkeypatch.setattr("app.routers.notes.db.get_note", get_note_mock)

    response = client.get("/notes/user-a-note-id")

    assert response.status_code == 404
    get_note_mock.assert_called_once_with("user-b", "user-a-note-id")


def test_review_analysis_not_found_returns_404(monkeypatch):
    _as_uid("uid-1")
    monkeypatch.setattr("app.routers.notes.db.submit_review", MagicMock(return_value=None))

    response = client.post(
        "/notes/note-1/analyses/analysis-1/review",
        json={"conditions": [], "documentation_gaps": [], "summary": "reviewed"},
    )

    assert response.status_code == 404
