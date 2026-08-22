from unittest.mock import MagicMock, patch

import pytest

from app import firestore_service as db


def _note_doc(note_id: str) -> MagicMock:
    doc = MagicMock()
    doc.id = note_id
    return doc


def _analysis_doc(review: dict | None) -> MagicMock:
    doc = MagicMock()
    doc.to_dict.return_value = {"review": review}
    return doc


@patch("app.firestore_service.get_db")
def test_compute_review_metrics_aggregates_by_condition(mock_get_db):
    mock_client = MagicMock()
    mock_get_db.return_value = mock_client

    notes_collection = mock_client.collection.return_value.document.return_value.collection.return_value
    notes_collection.stream.return_value = [_note_doc("note-1")]

    analyses_collection = notes_collection.document.return_value.collection.return_value
    review = {
        "conditions": [
            {"name": "Diabetes", "source": "ai", "rejected": False},
            {"name": "Diabetes", "source": "human_edited", "rejected": False},
            {"name": "Hypertension", "source": "ai", "rejected": True},
            {"name": "Knee pain", "source": "human_added", "rejected": False},
        ]
    }
    analyses_collection.stream.return_value = [_analysis_doc(review)]

    metrics = db.compute_review_metrics("uid-1")

    assert metrics.reviewed_analyses == 1
    assert metrics.total_conditions_suggested == 3  # 2x Diabetes (kept + edited) + 1x Hypertension (rejected)
    assert metrics.total_edited == 1
    assert metrics.total_rejected == 1
    assert metrics.total_added == 1
    assert metrics.correction_rate == pytest.approx(2 / 3)

    by_name = {c.name: c for c in metrics.by_condition}
    assert by_name["Diabetes"].times_suggested == 2
    assert by_name["Diabetes"].times_edited == 1
    assert by_name["Diabetes"].times_rejected == 0
    assert by_name["Hypertension"].times_rejected == 1
    assert by_name["Knee pain"].times_added == 1


@patch("app.firestore_service.get_db")
def test_compute_review_metrics_skips_unreviewed_analyses(mock_get_db):
    mock_client = MagicMock()
    mock_get_db.return_value = mock_client

    notes_collection = mock_client.collection.return_value.document.return_value.collection.return_value
    notes_collection.stream.return_value = [_note_doc("note-1")]

    analyses_collection = notes_collection.document.return_value.collection.return_value
    reviewed = {"conditions": [{"name": "Diabetes", "source": "ai", "rejected": False}]}
    analyses_collection.stream.return_value = [_analysis_doc(None), _analysis_doc(reviewed)]

    metrics = db.compute_review_metrics("uid-1")

    assert metrics.reviewed_analyses == 1
    assert metrics.total_conditions_suggested == 1


@patch("app.firestore_service.get_db")
def test_compute_review_metrics_handles_no_data_without_division_by_zero(mock_get_db):
    mock_client = MagicMock()
    mock_get_db.return_value = mock_client

    notes_collection = mock_client.collection.return_value.document.return_value.collection.return_value
    notes_collection.stream.return_value = []

    metrics = db.compute_review_metrics("uid-empty")

    assert metrics.reviewed_analyses == 0
    assert metrics.correction_rate == 0.0
    assert metrics.by_condition == []
