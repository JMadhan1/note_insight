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
from google.oauth2 import service_account

from .config import get_settings
from .models import (
    AnalysisResponse,
    AnalysisStatus,
    ConditionMetric,
    NoteCreateRequest,
    NoteListItem,
    NoteResponse,
    RecaptureReminder,
    ReviewMetrics,
    ReviewPayload,
    ReviewStatus,
    StoredAnalysisOutput,
)

_db: firestore.Client | None = None


def get_db() -> firestore.Client:
    """Lazy init, same pattern as auth.py: reuses the same service-account file
    already required for Firebase Admin, so there's one secret to configure, not
    two. Explicit credentials rather than google.auth.default() — this app never
    assumes it's running somewhere with Application Default Credentials set up
    (it isn't, locally)."""
    global _db
    if _db is None:
        settings = get_settings()
        credentials = service_account.Credentials.from_service_account_file(
            settings.firebase_service_account_path
        )
        _db = firestore.Client(project=credentials.project_id, credentials=credentials)
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
                latest_analysis_id=d.get("latestAnalysisId"),
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


def complete_analysis(
    uid: str,
    note_id: str,
    analysis_id: str,
    ai_output: StoredAnalysisOutput,
    recapture_reminders: list[RecaptureReminder] | None = None,
) -> None:
    _analyses_ref(uid, note_id).document(analysis_id).update(
        {
            "status": AnalysisStatus.COMPLETE.value,
            "aiOutput": ai_output.model_dump(mode="json"),
            "recaptureReminders": [r.model_dump(mode="json") for r in (recapture_reminders or [])],
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
        recapture_reminders=[RecaptureReminder(**r) for r in d.get("recaptureReminders", [])],
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


# ---------------------------------------------------------------------------
# Metrics — how often the human corrects the machine, broken down by condition
# ---------------------------------------------------------------------------

def compute_review_metrics(uid: str) -> ReviewMetrics:
    """Walks every reviewed analysis for this user and tallies, per condition name,
    how often the AI's suggestion was kept as-is, edited, rejected, or how often the
    human added a condition the AI never suggested at all.

    Not on the hot path (list_notes is), so a straightforward per-note fetch of the
    analyses subcollection is fine here rather than a collection-group query — this
    user's own note/analysis count is small enough that N+1 reads cost nothing
    meaningful, and it avoids needing a denormalized uid field just to support one
    infrequently-viewed page.
    """
    condition_stats: dict[str, dict[str, int]] = {}
    total_suggested = 0
    total_edited = 0
    total_rejected = 0
    total_added = 0
    reviewed_count = 0

    for note_doc in _notes_ref(uid).stream():
        for analysis_doc in _analyses_ref(uid, note_doc.id).stream():
            data = analysis_doc.to_dict()
            review = data.get("review")
            if not review:
                continue
            reviewed_count += 1

            for condition in review.get("conditions", []):
                name = (condition.get("name") or "").strip() or "(unnamed)"
                source = condition.get("source", "ai")
                rejected = bool(condition.get("rejected", False))
                stats = condition_stats.setdefault(
                    name, {"suggested": 0, "edited": 0, "rejected": 0, "added": 0}
                )

                if source == "human_added":
                    stats["added"] += 1
                    total_added += 1
                    continue

                stats["suggested"] += 1
                total_suggested += 1
                if rejected:
                    stats["rejected"] += 1
                    total_rejected += 1
                elif source == "human_edited":
                    stats["edited"] += 1
                    total_edited += 1

    by_condition = [
        ConditionMetric(
            name=name,
            times_suggested=stats["suggested"],
            times_edited=stats["edited"],
            times_rejected=stats["rejected"],
            times_added=stats["added"],
        )
        for name, stats in sorted(
            condition_stats.items(),
            key=lambda item: item[1]["suggested"] + item[1]["added"],
            reverse=True,
        )
    ]

    correction_rate = (total_edited + total_rejected) / total_suggested if total_suggested else 0.0

    return ReviewMetrics(
        reviewed_analyses=reviewed_count,
        total_conditions_suggested=total_suggested,
        total_edited=total_edited,
        total_rejected=total_rejected,
        total_added=total_added,
        correction_rate=correction_rate,
        by_condition=by_condition,
    )


# ---------------------------------------------------------------------------
# Cross-visit recapture reminders — the real 'annual recapture' gap: CMS
# resets risk scores every January 1 and doesn't carry chronic diagnoses
# forward automatically, so a condition the patient still has silently stops
# counting once nobody re-documents it at a later visit.
# ---------------------------------------------------------------------------

def find_recapture_reminders(
    uid: str,
    pseudonym: str | None,
    exclude_note_id: str,
    current_condition_names: set[str],
    limit: int = 10,
) -> list[RecaptureReminder]:
    """Looks at this patient's other visits (matched by pseudonym — the only
    patient-linking field this product has) and flags chronic conditions that
    were documented before but aren't mentioned today.

    Deliberately filters by pseudonym alone, with no order_by, and sorts in
    Python instead: a compound Firestore query (where + order_by on different
    fields) needs a manually-created composite index, which would mean this
    feature silently 500s in a fresh deployment until someone clicks a
    Firebase console link. A single-field equality filter needs no such setup
    — the tradeoff is a little more work done server-side, in exchange for
    the whole app still being 'clone it and run it' with zero manual
    Firestore configuration.
    """
    if not pseudonym or not pseudonym.strip():
        return []

    matching_notes = [
        doc for doc in _notes_ref(uid).where("pseudonym", "==", pseudonym).stream() if doc.id != exclude_note_id
    ]
    matching_notes.sort(key=lambda doc: doc.to_dict().get("createdAt"), reverse=True)

    normalized_current = {name.strip().lower() for name in current_condition_names}
    seen: dict[str, RecaptureReminder] = {}

    for note_doc in matching_notes[:limit]:
        note_data = note_doc.to_dict()
        latest_analysis_id = note_data.get("latestAnalysisId")
        if not latest_analysis_id:
            continue
        analysis_snap = _analyses_ref(uid, note_doc.id).document(latest_analysis_id).get()
        if not analysis_snap.exists:
            continue
        analysis_data = analysis_snap.to_dict()
        # Prefer the human-reviewed version when it exists — a condition the
        # clinician rejected shouldn't come back to haunt a later visit.
        source = analysis_data.get("review") or analysis_data.get("aiOutput")
        if not source:
            continue

        for condition in source.get("conditions", []):
            if condition.get("rejected"):
                continue
            name = (condition.get("name") or "").strip()
            if not name:
                continue
            normalized = name.lower()
            if normalized in normalized_current or normalized in seen:
                continue
            seen[normalized] = RecaptureReminder(
                condition_name=name,
                last_documented_at=note_data["createdAt"],
                last_note_id=note_doc.id,
                last_analysis_id=latest_analysis_id,
            )

    return list(seen.values())
