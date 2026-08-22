import logging
import re
from collections.abc import Generator

from google import genai
from google.genai import types

from .config import get_settings
from .models import AIAnalysisOutput, ConditionSource, StoredAnalysisOutput, StoredCondition
from .prompts.note_analysis_prompt import build_prompt

logger = logging.getLogger(__name__)

_client: genai.Client | None = None


class AnalysisFailure(Exception):
    """Raised when Gemini's output could not be turned into a valid, schema-conforming
    analysis after all retry attempts. Callers decide what to persist/show on this —
    see routers/notes.py, which stores a 'failed' analysis rather than losing the note."""


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = get_settings().gemini_api_key
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not configured. Set it in backend/.env before analyzing notes."
            )
        _client = genai.Client(api_key=api_key)
    return _client


def _normalize(text: str) -> str:
    """Lowercase, collapse whitespace, and drop punctuation so that minor formatting
    differences (an extra space, a smart quote, a trailing period) don't cause a
    real quote to be falsely flagged as fabricated."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def verify_quote(quote: str, note_text: str) -> bool:
    """True only if `quote` is a verbatim (normalized) substring of `note_text`.
    This is the mechanism that answers 'how do you know the model didn't make this up?' —
    every evidence quote is checked against the source note, not just trusted."""
    if not quote.strip():
        return False
    return _normalize(quote) in _normalize(note_text)


def _build_stored_output(parsed: AIAnalysisOutput, note_text: str) -> StoredAnalysisOutput:
    """Shared by run_analysis and the streaming path: turns Gemini's validated schema
    output into the stored shape, running quote verification exactly once, in one place,
    so streaming and non-streaming analyses can never drift in how they check evidence."""
    stored_conditions = [
        StoredCondition(
            **condition.model_dump(),
            quote_verified=verify_quote(condition.evidence_quote, note_text),
            source=ConditionSource.AI,
            rejected=False,
        )
        for condition in parsed.conditions
    ]
    return StoredAnalysisOutput(
        conditions=stored_conditions,
        documentation_gaps=parsed.documentation_gaps,
        summary=parsed.summary,
    )


def run_analysis(note_text: str, max_attempts: int = 2) -> tuple[StoredAnalysisOutput, str]:
    """Calls Gemini with a schema-constrained request, validates the result against
    AIAnalysisOutput (Pydantic), verifies every evidence quote against the source note,
    and retries once on a malformed/invalid response before giving up.

    Returns (stored_output, model_version_used). Raises AnalysisFailure if every
    attempt fails validation or the API call itself errors out.
    """
    settings = get_settings()
    client = _get_client()
    base_prompt = build_prompt(note_text)

    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        prompt = base_prompt
        if attempt > 1:
            prompt += (
                "\n\nNOTE: your previous response did not match the required JSON schema. "
                "Return ONLY valid JSON matching the schema exactly, with no extra fields "
                "and no commentary."
            )

        try:
            response = client.models.generate_content(
                model=settings.gemini_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=AIAnalysisOutput,
                    temperature=0.2,
                ),
            )

            parsed: AIAnalysisOutput | None = response.parsed
            if parsed is None:
                # SDK couldn't parse/validate against the schema at all.
                raise ValueError(f"Gemini response did not match the schema: {response.text!r}")

            return _build_stored_output(parsed, note_text), settings.gemini_model

        except Exception as exc:  # schema validation failure, API error, network error, etc.
            logger.warning("Gemini analysis attempt %d/%d failed: %s", attempt, max_attempts, exc)
            last_error = exc

    raise AnalysisFailure(f"Analysis failed after {max_attempts} attempt(s): {last_error}")


def stream_analysis_text(note_text: str) -> Generator[str, None, None]:
    """Yields raw JSON text deltas as Gemini generates the schema-constrained response,
    for a live 'watch it think' preview in the UI. Deliberately does no validation or
    retry here — the caller accumulates the full text and hands it to
    build_streamed_output() once the stream ends, which runs the exact same schema
    validation and quote verification as the non-streaming path. Streaming only changes
    what the user sees while waiting; it never weakens what gets trusted and saved."""
    settings = get_settings()
    client = _get_client()
    prompt = build_prompt(note_text)

    stream = client.models.generate_content_stream(
        model=settings.gemini_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=AIAnalysisOutput,
            temperature=0.2,
        ),
    )
    for chunk in stream:
        if chunk.text:
            yield chunk.text


def build_streamed_output(accumulated_text: str, note_text: str) -> StoredAnalysisOutput:
    """Validates the fully-accumulated streamed text against the schema. Raises
    (ValueError/pydantic ValidationError) on malformed output — the router catches
    that and falls back to run_analysis()'s own retry, rather than duplicating retry
    logic here."""
    parsed = AIAnalysisOutput.model_validate_json(accumulated_text)
    return _build_stored_output(parsed, note_text)


_TRANSCRIBE_PROMPT = (
    "Transcribe the clinical note shown in this file into plain text, exactly as written. "
    "Preserve line breaks where they aid readability. Return only the transcribed text — "
    "no commentary, no markdown formatting, no summary."
)


def transcribe_document(file_bytes: bytes, mime_type: str) -> str:
    """Sends an uploaded image or PDF of a handwritten/printed note directly to Gemini's
    multimodal input and asks for a plain-text transcription — no separate OCR step.
    The returned text is meant to land in the same note textarea typing and dictation
    both fill, then flow through the exact same validated /notes pipeline; this function
    never bypasses schema validation or quote verification, it only gets text INTO the
    note in the first place."""
    client = _get_client()
    settings = get_settings()
    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=[
            types.Part.from_bytes(data=file_bytes, mime_type=mime_type),
            _TRANSCRIBE_PROMPT,
        ],
    )
    return (response.text or "").strip()
