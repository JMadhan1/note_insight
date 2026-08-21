from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class DocumentationStatus(str, Enum):
    WELL_DOCUMENTED = "well_documented"
    AMBIGUOUS = "ambiguous"
    MENTIONED_NO_ASSESSMENT = "mentioned_without_assessment_or_plan"


class ConditionSource(str, Enum):
    AI = "ai"
    HUMAN_EDITED = "human_edited"
    HUMAN_ADDED = "human_added"


class AnalysisStatus(str, Enum):
    PENDING = "pending"
    COMPLETE = "complete"
    FAILED = "failed"


class ReviewStatus(str, Enum):
    PENDING = "pending"
    REVIEWED = "reviewed"


# ---------------------------------------------------------------------------
# Schema Gemini's response is constrained to (passed directly as response_schema)
# ---------------------------------------------------------------------------

class AIConditionModel(BaseModel):
    name: str = Field(..., min_length=1, description="Clinical condition name, e.g. 'Type 2 Diabetes Mellitus'")
    evidence_quote: str = Field(
        ..., min_length=1,
        description="A verbatim quote copied exactly from the note text supporting this condition",
    )
    documentation_status: DocumentationStatus
    icd10_code: str = Field(..., min_length=1, description="Best-guess ICD-10 code; approximate is acceptable")
    confidence: float = Field(..., ge=0.0, le=1.0)


class AIAnalysisOutput(BaseModel):
    conditions: list[AIConditionModel]
    documentation_gaps: list[str]
    summary: str


# ---------------------------------------------------------------------------
# What we store and serve — adds server-computed and human-review fields
# ---------------------------------------------------------------------------

class StoredCondition(AIConditionModel):
    quote_verified: bool
    source: ConditionSource = ConditionSource.AI
    rejected: bool = False


class StoredAnalysisOutput(BaseModel):
    conditions: list[StoredCondition]
    documentation_gaps: list[str]
    summary: str


class ReviewPayload(BaseModel):
    """Body of a review submission — the human-edited version of an analysis."""
    conditions: list[StoredCondition]
    documentation_gaps: list[str]
    summary: str


# ---------------------------------------------------------------------------
# API request/response contracts
# ---------------------------------------------------------------------------

class NoteCreateRequest(BaseModel):
    # The brief expects 100-3000 words typically, but robustness is explicitly tested with a
    # 5000-word note (~28k characters average English word length) — this cap is set well above
    # that, not at the expected/typical length, so that case actually succeeds rather than 422s.
    note_text: str = Field(..., min_length=1, max_length=60000)
    pseudonym: str | None = Field(default=None, max_length=100)
    visit_date: str | None = None  # ISO date string (YYYY-MM-DD), optional

    @field_validator("note_text")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("note_text cannot be blank or whitespace-only")
        return v


class AnalysisResponse(BaseModel):
    id: str
    note_id: str
    created_at: datetime
    model_version: str
    prompt_version: str
    status: AnalysisStatus
    ai_output: StoredAnalysisOutput | None
    review: StoredAnalysisOutput | None
    review_status: ReviewStatus
    error_message: str | None = None


class NoteResponse(BaseModel):
    id: str
    note_text: str
    pseudonym: str | None
    visit_date: str | None
    created_at: datetime
    latest_analysis_id: str | None


class NoteListItem(BaseModel):
    id: str
    pseudonym: str | None
    visit_date: str | None
    created_at: datetime
    condition_count: int
    review_status: ReviewStatus
    latest_analysis_id: str | None


class NoteWithAnalysis(BaseModel):
    note: NoteResponse
    analysis: AnalysisResponse
