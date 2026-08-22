from fastapi import APIRouter, Depends, HTTPException, status

from .. import firestore_service as db
from ..auth import get_current_uid
from ..config import get_settings
from ..gemini_service import AnalysisFailure, run_analysis
from ..models import (
    AnalysisResponse,
    NoteCreateRequest,
    NoteListItem,
    NoteResponse,
    NoteWithAnalysis,
    ReviewMetrics,
    ReviewPayload,
)
from ..prompts.note_analysis_prompt import PROMPT_VERSION
from ..rate_limit import enforce_note_submission_rate_limit

router = APIRouter(prefix="/notes", tags=["notes"])


@router.post("", response_model=NoteWithAnalysis, status_code=status.HTTP_201_CREATED)
def submit_note(payload: NoteCreateRequest, uid: str = Depends(get_current_uid)) -> NoteWithAnalysis:
    """Creates the note, then immediately runs the AI analysis synchronously.
    A note is never left without an analysis record: on failure we still store a
    'failed' analysis with the error, rather than silently dropping the submission."""
    enforce_note_submission_rate_limit(uid)
    note = db.create_note(uid, payload)
    settings = get_settings()
    analysis_id = db.create_analysis_pending(uid, note.id, settings.gemini_model, PROMPT_VERSION)

    try:
        output, _model_used = run_analysis(payload.note_text)
        db.complete_analysis(uid, note.id, analysis_id, output)
    except AnalysisFailure as exc:
        db.fail_analysis(uid, note.id, analysis_id, str(exc))
    except RuntimeError as exc:
        # e.g. GEMINI_API_KEY not configured yet
        db.fail_analysis(uid, note.id, analysis_id, str(exc))

    refreshed_note = db.get_note(uid, note.id)
    analysis = db.get_analysis(uid, note.id, analysis_id)
    if refreshed_note is None or analysis is None:
        raise HTTPException(status_code=500, detail="Note or analysis vanished immediately after creation")
    return NoteWithAnalysis(note=refreshed_note, analysis=analysis)


@router.get("", response_model=list[NoteListItem])
def list_notes(uid: str = Depends(get_current_uid)) -> list[NoteListItem]:
    return db.list_notes(uid)


@router.get("/metrics", response_model=ReviewMetrics)
def get_review_metrics(uid: str = Depends(get_current_uid)) -> ReviewMetrics:
    """Declared before /{note_id} — otherwise FastAPI would match 'metrics' as a
    note id and this route would never be reached."""
    return db.compute_review_metrics(uid)


@router.get("/{note_id}", response_model=NoteResponse)
def get_note(note_id: str, uid: str = Depends(get_current_uid)) -> NoteResponse:
    note = db.get_note(uid, note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    return note


@router.get("/{note_id}/analyses/{analysis_id}", response_model=AnalysisResponse)
def get_analysis(note_id: str, analysis_id: str, uid: str = Depends(get_current_uid)) -> AnalysisResponse:
    analysis = db.get_analysis(uid, note_id, analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return analysis


@router.post("/{note_id}/analyses/{analysis_id}/review", response_model=AnalysisResponse)
def review_analysis(
    note_id: str, analysis_id: str, payload: ReviewPayload, uid: str = Depends(get_current_uid)
) -> AnalysisResponse:
    analysis = db.submit_review(uid, note_id, analysis_id, payload)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return analysis
