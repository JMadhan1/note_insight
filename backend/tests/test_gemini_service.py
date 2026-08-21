from unittest.mock import MagicMock, patch

import pytest

from app.gemini_service import AnalysisFailure, run_analysis
from app.models import AIAnalysisOutput, AIConditionModel


def _fake_response(parsed):
    resp = MagicMock()
    resp.parsed = parsed
    resp.text = "irrelevant"
    return resp


@patch("app.gemini_service._get_client")
def test_run_analysis_raises_after_exhausting_retries(mock_get_client):
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = ValueError("boom")
    mock_get_client.return_value = mock_client

    with pytest.raises(AnalysisFailure):
        run_analysis("some note text", max_attempts=2)

    assert mock_client.models.generate_content.call_count == 2


@patch("app.gemini_service._get_client")
def test_run_analysis_retries_once_then_succeeds(mock_get_client):
    good_parsed = AIAnalysisOutput(
        conditions=[],
        documentation_gaps=[],
        summary="Encounter for a minor complaint.",
    )
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = [
        _fake_response(None),  # first attempt: unparseable
        _fake_response(good_parsed),  # second attempt: succeeds
    ]
    mock_get_client.return_value = mock_client

    output, model = run_analysis("Patient has a mild cold.", max_attempts=2)

    assert output.summary == "Encounter for a minor complaint."
    assert mock_client.models.generate_content.call_count == 2


@patch("app.gemini_service._get_client")
def test_run_analysis_marks_unverifiable_quote(mock_get_client):
    parsed = AIAnalysisOutput(
        conditions=[
            AIConditionModel(
                name="Diabetes",
                evidence_quote="this exact text is not in the note",
                documentation_status="ambiguous",
                icd10_code="E11.9",
                confidence=0.7,
            )
        ],
        documentation_gaps=[],
        summary="summary",
    )
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _fake_response(parsed)
    mock_get_client.return_value = mock_client

    output, _ = run_analysis("The patient has hypertension.", max_attempts=2)

    assert output.conditions[0].quote_verified is False


@patch("app.gemini_service._get_client")
def test_run_analysis_verifies_real_quote(mock_get_client):
    parsed = AIAnalysisOutput(
        conditions=[
            AIConditionModel(
                name="Hypertension",
                evidence_quote="patient has hypertension",
                documentation_status="ambiguous",
                icd10_code="I10",
                confidence=0.9,
            )
        ],
        documentation_gaps=[],
        summary="summary",
    )
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _fake_response(parsed)
    mock_get_client.return_value = mock_client

    output, _ = run_analysis("The patient has hypertension, well controlled.", max_attempts=2)

    assert output.conditions[0].quote_verified is True
