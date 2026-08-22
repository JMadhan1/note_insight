import json
import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from .. import firestore_service as db
from ..auth import get_current_uid
from ..config import get_settings
from ..gemini_service import (
    AnalysisFailure,
    build_streamed_output,
    run_analysis,
    stream_analysis_text,
    transcribe_document,
)
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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notes", tags=["notes"])

_ALLOWED_UPLOAD_TYPES = {"image/jpeg", "image/png", "image/webp", "application/pdf"}
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10MB


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


@router.post("/extract-text")
async def extract_note_text(
    file: UploadFile = File(...), uid: str = Depends(get_current_uid)
) -> dict[str, str]:
    """Reads a photographed or scanned note (image or PDF) and transcribes it to plain
    text via Gemini's multimodal input — no separate OCR dependency. The extracted text
    is returned to fill the note textarea for the clinician to review, exactly like
    dictated or typed text; it is NOT saved directly. Nothing here bypasses schema
    validation or quote verification — those only ever happen once real note_text is
    submitted through the normal /notes (or /notes/stream) endpoint."""
    if file.content_type not in _ALLOWED_UPLOAD_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only JPEG, PNG, WEBP images or PDF files are supported",
        )

    contents = await file.read()
    if len(contents) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File too large — max 10MB")

    try:
        text = transcribe_document(contents, file.content_type)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Could not read this file: {exc}"
        ) from exc

    if not text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Could not find any readable text in this file",
        )

    return {"extracted_text": text}


@router.post("/stream")
def submit_note_streaming(payload: NoteCreateRequest, uid: str = Depends(get_current_uid)) -> StreamingResponse:
    """Same guarantees as POST /notes (schema validation, quote verification, the note
    is saved before analysis even starts, a failure never loses the note) — the only
    difference is the client sees Gemini's raw JSON arrive incrementally instead of
    waiting on a blank screen for the full response. If the streamed text doesn't
    validate, this falls back to run_analysis() (which retries once internally) rather
    than duplicating retry logic here."""
    enforce_note_submission_rate_limit(uid)
    note = db.create_note(uid, payload)
    settings = get_settings()
    analysis_id = db.create_analysis_pending(uid, note.id, settings.gemini_model, PROMPT_VERSION)

    def event_stream():
        accumulated = ""
        try:
            for delta in stream_analysis_text(payload.note_text):
                accumulated += delta
                yield f"event: delta\ndata: {json.dumps({'text': delta})}\n\n"

            try:
                output = build_streamed_output(accumulated, payload.note_text)
            except (ValidationError, ValueError) as exc:
                logger.warning("Streamed output failed validation, falling back: %s", exc)
                output, _model = run_analysis(payload.note_text)

            db.complete_analysis(uid, note.id, analysis_id, output)
            yield f"event: complete\ndata: {json.dumps({'note_id': note.id, 'analysis_id': analysis_id})}\n\n"

        except (AnalysisFailure, RuntimeError) as exc:
            db.fail_analysis(uid, note.id, analysis_id, str(exc))
            yield (
                f"event: error\ndata: "
                f"{json.dumps({'note_id': note.id, 'analysis_id': analysis_id, 'message': str(exc)})}\n\n"
            )

    return StreamingResponse(event_stream(), media_type="text/event-stream")


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
