from unittest.mock import MagicMock, patch

from app import firestore_service as db


def _note_doc(note_id: str, pseudonym: str, latest_analysis_id: str, created_at) -> MagicMock:
    doc = MagicMock()
    doc.id = note_id
    doc.to_dict.return_value = {
        "pseudonym": pseudonym,
        "latestAnalysisId": latest_analysis_id,
        "createdAt": created_at,
    }
    return doc


def _analysis_doc(conditions: list[dict], reviewed: bool = False) -> MagicMock:
    doc = MagicMock()
    output = {"conditions": conditions, "documentation_gaps": [], "summary": "x"}
    doc.to_dict.return_value = {"aiOutput": output, "review": output if reviewed else None}
    return doc


def test_no_pseudonym_returns_no_reminders():
    # Short-circuits before touching Firestore at all — safe to call with no mocking.
    result = db.find_recapture_reminders("uid-1", None, "note-current", {"Diabetes"})
    assert result == []

    result = db.find_recapture_reminders("uid-1", "   ", "note-current", {"Diabetes"})
    assert result == []


@patch("app.firestore_service.get_db")
def test_flags_condition_missing_from_current_visit(mock_get_db):
    mock_client = MagicMock()
    mock_get_db.return_value = mock_client

    notes_collection = mock_client.collection.return_value.document.return_value.collection.return_value
    notes_collection.where.return_value.stream.return_value = [
        _note_doc("note-past", "P-001", "analysis-past", "2026-01-01T00:00:00Z"),
    ]

    analyses_collection = notes_collection.document.return_value.collection.return_value
    analyses_collection.document.return_value.get.return_value = _analysis_doc(
        [{"name": "Diabetes", "rejected": False}, {"name": "Hypertension", "rejected": False}]
    )

    reminders = db.find_recapture_reminders("uid-1", "P-001", "note-current", {"Hypertension"})

    assert len(reminders) == 1
    assert reminders[0].condition_name == "Diabetes"
    assert reminders[0].last_note_id == "note-past"
    assert reminders[0].last_analysis_id == "analysis-past"


@patch("app.firestore_service.get_db")
def test_excludes_the_current_note_itself(mock_get_db):
    mock_client = MagicMock()
    mock_get_db.return_value = mock_client

    notes_collection = mock_client.collection.return_value.document.return_value.collection.return_value
    notes_collection.where.return_value.stream.return_value = [
        _note_doc("note-current", "P-001", "analysis-current", "2026-01-01T00:00:00Z"),
    ]

    reminders = db.find_recapture_reminders("uid-1", "P-001", "note-current", set())

    assert reminders == []


@patch("app.firestore_service.get_db")
def test_ignores_rejected_conditions_from_past_visits(mock_get_db):
    mock_client = MagicMock()
    mock_get_db.return_value = mock_client

    notes_collection = mock_client.collection.return_value.document.return_value.collection.return_value
    notes_collection.where.return_value.stream.return_value = [
        _note_doc("note-past", "P-001", "analysis-past", "2026-01-01T00:00:00Z"),
    ]
    analyses_collection = notes_collection.document.return_value.collection.return_value
    analyses_collection.document.return_value.get.return_value = _analysis_doc(
        [{"name": "Diabetes", "rejected": True}]
    )

    reminders = db.find_recapture_reminders("uid-1", "P-001", "note-current", set())

    assert reminders == []


@patch("app.firestore_service.get_db")
def test_prefers_reviewed_conditions_over_ai_output(mock_get_db):
    """If the clinician rejected a condition during review, it must not haunt a
    later visit just because the AI originally suggested it."""
    mock_client = MagicMock()
    mock_get_db.return_value = mock_client

    notes_collection = mock_client.collection.return_value.document.return_value.collection.return_value
    notes_collection.where.return_value.stream.return_value = [
        _note_doc("note-past", "P-001", "analysis-past", "2026-01-01T00:00:00Z"),
    ]
    analyses_collection = notes_collection.document.return_value.collection.return_value
    doc = MagicMock()
    doc.to_dict.return_value = {
        "aiOutput": {"conditions": [{"name": "Diabetes", "rejected": False}], "documentation_gaps": [], "summary": "x"},
        "review": {"conditions": [{"name": "Diabetes", "rejected": True}], "documentation_gaps": [], "summary": "x"},
    }
    analyses_collection.document.return_value.get.return_value = doc

    reminders = db.find_recapture_reminders("uid-1", "P-001", "note-current", set())

    assert reminders == []


@patch("app.firestore_service.get_db")
def test_no_matching_pseudonym_history_returns_empty(mock_get_db):
    mock_client = MagicMock()
    mock_get_db.return_value = mock_client
    notes_collection = mock_client.collection.return_value.document.return_value.collection.return_value
    notes_collection.where.return_value.stream.return_value = []

    reminders = db.find_recapture_reminders("uid-1", "P-999", "note-current", set())

    assert reminders == []
