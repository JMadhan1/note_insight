import pytest
from pydantic import ValidationError

from app.models import AIAnalysisOutput, AIConditionModel, NoteCreateRequest


def test_valid_ai_condition():
    c = AIConditionModel(
        name="Type 2 Diabetes",
        evidence_quote="the patient has type 2 diabetes",
        documentation_status="ambiguous",
        icd10_code="E11.9",
        confidence=0.8,
    )
    assert c.confidence == 0.8


def test_confidence_above_range_rejected():
    with pytest.raises(ValidationError):
        AIConditionModel(
            name="X", evidence_quote="x", documentation_status="ambiguous",
            icd10_code="E11.9", confidence=1.5,
        )


def test_confidence_below_range_rejected():
    with pytest.raises(ValidationError):
        AIConditionModel(
            name="X", evidence_quote="x", documentation_status="ambiguous",
            icd10_code="E11.9", confidence=-0.1,
        )


def test_invalid_documentation_status_rejected():
    with pytest.raises(ValidationError):
        AIConditionModel(
            name="X", evidence_quote="x", documentation_status="not_a_real_status",
            icd10_code="E11.9", confidence=0.5,
        )


def test_empty_evidence_quote_rejected():
    with pytest.raises(ValidationError):
        AIConditionModel(
            name="X", evidence_quote="", documentation_status="ambiguous",
            icd10_code="E11.9", confidence=0.5,
        )


def test_analysis_output_requires_list_of_conditions():
    with pytest.raises(ValidationError):
        AIAnalysisOutput(conditions="not-a-list", documentation_gaps=[], summary="s")


def test_note_create_rejects_blank_text():
    with pytest.raises(ValidationError):
        NoteCreateRequest(note_text="   ")


def test_note_create_rejects_oversized_text():
    with pytest.raises(ValidationError):
        NoteCreateRequest(note_text="a" * 20001)


def test_note_create_accepts_valid_text():
    n = NoteCreateRequest(note_text="Patient presents with cough.", pseudonym="P-001")
    assert n.pseudonym == "P-001"
