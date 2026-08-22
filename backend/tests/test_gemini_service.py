from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from app.gemini_service import (
    AnalysisFailure,
    build_streamed_output,
    run_analysis,
    stream_analysis_text,
    transcribe_document,
)
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
                status_reason="Type and control status are not stated.",
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
                status_reason="Severity and current treatment plan are not stated.",
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


def _fake_stream_chunk(text):
    chunk = MagicMock()
    chunk.text = text
    return chunk


@patch("app.gemini_service._get_client")
def test_stream_analysis_text_yields_each_chunk(mock_get_client):
    mock_client = MagicMock()
    mock_client.models.generate_content_stream.return_value = [
        _fake_stream_chunk('{"conditions":'),
        _fake_stream_chunk("[]," ),
        _fake_stream_chunk('"documentation_gaps":[],"summary":"ok"}'),
    ]
    mock_get_client.return_value = mock_client

    chunks = list(stream_analysis_text("Patient has a cold."))

    assert chunks == ['{"conditions":', "[],", '"documentation_gaps":[],"summary":"ok"}']


@patch("app.gemini_service._get_client")
def test_stream_analysis_text_skips_empty_chunks(mock_get_client):
    """The SDK can yield chunks with no text (e.g. metadata-only) — these must not
    become empty deltas sent to the client."""
    mock_client = MagicMock()
    mock_client.models.generate_content_stream.return_value = [
        _fake_stream_chunk("hello"),
        _fake_stream_chunk(None),
        _fake_stream_chunk(""),
    ]
    mock_get_client.return_value = mock_client

    chunks = list(stream_analysis_text("Patient has a cold."))

    assert chunks == ["hello"]


def test_build_streamed_output_validates_and_verifies_quotes():
    note_text = "Patient has hypertension, well controlled on lisinopril."
    accumulated = (
        '{"conditions":[{"name":"Hypertension","evidence_quote":"has hypertension",'
        '"documentation_status":"well_documented","status_reason":"Well controlled and treated.",'
        '"icd10_code":"I10","confidence":0.9}],"documentation_gaps":[],"summary":"Routine visit."}'
    )

    output = build_streamed_output(accumulated, note_text)

    assert len(output.conditions) == 1
    assert output.conditions[0].quote_verified is True


def test_build_streamed_output_raises_on_malformed_json():
    with pytest.raises(ValidationError):
        build_streamed_output("{not valid json at all", "some note")


def test_build_streamed_output_raises_on_incomplete_json():
    """Simulates a stream that got cut off mid-response — must fail cleanly so the
    router's fallback to run_analysis() kicks in, not crash."""
    with pytest.raises(ValidationError):
        build_streamed_output('{"conditions": [{"name": "Diabetes"', "some note")


@patch("app.gemini_service._get_client")
def test_transcribe_document_returns_stripped_text(mock_get_client):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "  Patient has a cough.  \n"
    mock_client.models.generate_content.return_value = mock_response
    mock_get_client.return_value = mock_client

    text = transcribe_document(b"fake-image-bytes", "image/png")

    assert text == "Patient has a cough."


@patch("app.gemini_service._get_client")
def test_transcribe_document_returns_empty_string_not_none(mock_get_client):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = None
    mock_client.models.generate_content.return_value = mock_response
    mock_get_client.return_value = mock_client

    text = transcribe_document(b"fake-image-bytes", "image/png")

    assert text == ""
