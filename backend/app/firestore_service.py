"""Data access layer. Every function is scoped by `uid`, sourced only from the
verified token (see auth.get_current_uid) — never from a client-supplied path or
body field — so cross-user access is structurally impossible here, not just
policed by convention.

Firestore layout:
  users/{uid}/notes/{noteId}
  users/{uid}/notes/{noteId}/analyses/{analysisId}

See PROJECT_PLAN.md section 0.2/0.3 for the full reasoning.
"""

from datetime import datetime, timezone

from google.cloud import firestore

from .models import (
    AnalysisResponse,
    AnalysisStatus,
    NoteCreateRequest,
    NoteListItem,
    NoteResponse,
    ReviewPayload,
    ReviewStatus,
    StoredAnalysisOutput,
)

_db: firestore.Client | None = None


def get_db() -> firestore.Client:
    global _db
    if _db is None:
        _db = firestore.Client()
    return _db


def _notes_ref(uid: str):
    return get_db().collection("users").document(uid).collection("notes")


def _analyses_ref(uid: str, note_id: str):
    return _notes_ref(uid).document(note_id).collection("analyses")


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------

def create_note(uid: str, payload: NoteCreateRequest) -> NoteResponse:
    ref = _notes_ref(uid).document()
    data = {
        "noteText": payload.note_text,
        "pseudonym": payload.pseudonym,
        "visitDate": payload.visit_date,
        "createdAt": datetime.now(timezone.utc),
        "latestAnalysisId": None,
        "latestConditionCount": 0,
        "latestReviewStatus": ReviewStatus.PENDING.value,
    }
    ref.set(data)
    return NoteResponse(
        id=ref.id,
        note_text=data["noteText"],
        pseudonym=data["pseudonym"],
        visit_date=data["visitDate"],
        created_at=data["createdAt"],
        latest_analysis_id=None,
    )


def get_note(uid: str, note_id: str) -> NoteResponse | None:
    snap = _notes_ref(uid).document(note_id).get()
    if not snap.exists:
        return None
    d = snap.to_dict()
    return NoteResponse(
        id=snap.id,
        note_text=d["noteText"],
        pseudonym=d.get("pseudonym"),
        visit_date=d.get("visitDate"),
        created_at=d["createdAt"],
        latest_analysis_id=d.get("latestAnalysisId"),
    )


def list_notes(uid: str, limit: int = 50) -> list[NoteListItem]:
    """Single query, newest first. condition_count/review_status are denormalized
    onto the note document (updated in complete_analysis/fail_analysis/submit_review
    below) specifically so this list doesn't do an N+1 fetch into the analyses
    subcollection for every row."""
    docs = (
        _notes_ref(uid)
        .order_by("createdAt", direction=firestore.Query.DESCENDING)
        .limit(limit)
        .stream()
    )
    items = []
    for doc in docs:
        d = doc.to_dict()
        items.append(
            NoteListItem(
                id=doc.id,
                pseudonym=d.get("pseudonym"),
                visit_date=d.get("visitDate"),
                created_at=d["createdAt"],
                condition_count=d.get("latestConditionCount", 0),
                review_status=ReviewStatus(d.get("latestReviewStatus", "pending")),
            )
        )
    return items


# ---------------------------------------------------------------------------
# Analyses
# ---------------------------------------------------------------------------

def create_analysis_pending(uid: str, note_id: str, model_version: str, prompt_version: str) -> str:
    ref = _analyses_ref(uid, note_id).document()
    ref.set(
        {
            "createdAt": datetime.now(timezone.utc),
            "modelVersion": model_version,
            "promptVersion": prompt_version,
            "status": AnalysisStatus.PENDING.value,
            "aiOutput": None,
            "review": None,
            "reviewStatus": ReviewStatus.PENDING.value,
            "errorMessage": None,
        }
    )
    return ref.id


def complete_analysis(uid: str, note_id: str, analysis_id: str, ai_output: StoredAnalysisOutput) -> None:
    _analyses_ref(uid, note_id).document(analysis_id).update(
        {
            "status": AnalysisStatus.COMPLETE.value,
            "aiOutput": ai_output.model_dump(mode="json"),
        }
    )
    _notes_ref(uid).document(note_id).update(
        {
            "latestAnalysisId": analysis_id,
            "latestConditionCount": len(ai_output.conditions),
            "latestReviewStatus": ReviewStatus.PENDING.value,
        }
    )


def fail_analysis(uid: str, note_id: str, analysis_id: str, error_message: str) -> None:
    _analyses_ref(uid, note_id).document(analysis_id).update(
        {
            "status": AnalysisStatus.FAILED.value,
            "errorMessage": error_message,
        }
    )
    _notes_ref(uid).document(note_id).update(
        {
            "latestAnalysisId": analysis_id,
            "latestConditionCount": 0,
            "latestReviewStatus": ReviewStatus.PENDING.value,
        }
    )


def _analysis_from_dict(note_id: str, analysis_id: str, d: dict) -> AnalysisResponse:
    return AnalysisResponse(
        id=analysis_id,
        note_id=note_id,
        created_at=d["createdAt"],
        model_version=d.get("modelVersion", ""),
        prompt_version=d.get("promptVersion", ""),
        status=AnalysisStatus(d.get("status", "pending")),
        ai_output=StoredAnalysisOutput(**d["aiOutput"]) if d.get("aiOutput") else None,
        review=StoredAnalysisOutput(**d["review"]) if d.get("review") else None,
        review_status=ReviewStatus(d.get("reviewStatus", "pending")),
        error_message=d.get("errorMessage"),
    )


def get_analysis(uid: str, note_id: str, analysis_id: str) -> AnalysisResponse | None:
    snap = _analyses_ref(uid, note_id).document(analysis_id).get()
    if not snap.exists:
        return None
    return _analysis_from_dict(note_id, snap.id, snap.to_dict())


def submit_review(uid: str, note_id: str, analysis_id: str, review: ReviewPayload) -> AnalysisResponse | None:
    """Writes the human-reviewed version alongside the original. `aiOutput` is never
    touched by this function — the original model output stays intact forever."""
    ref = _analyses_ref(uid, note_id).document(analysis_id)
    snap = ref.get()
    if not snap.exists:
        return None

    review_dict = review.model_dump(mode="json")
    ref.update(
        {
            "review": review_dict,
            "reviewStatus": ReviewStatus.REVIEWED.value,
        }
    )
    _notes_ref(uid).document(note_id).update(
        {
            "latestConditionCount": len(review.conditions),
            "latestReviewStatus": ReviewStatus.REVIEWED.value,
        }
    )

    updated = ref.get().to_dict()
    return _analysis_from_dict(note_id, analysis_id, updated)
