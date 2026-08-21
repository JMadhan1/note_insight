import { useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { submitNote } from "../api/notes";
import { ApiError } from "../api/client";
import { SparkleIcon } from "../components/icons";

type SubmitState = "idle" | "submitting" | "error";

// The brief describes 100-3000 words as the typical range, but robustness is explicitly
// tested with a 5000-word note — that must still submit, just with a heads-up, not a block.
// The hard ceiling matches the backend's actual cap (60,000 chars, NoteCreateRequest.note_text)
// converted to a safe word-count estimate, so the button only disables when a submission would
// genuinely be rejected server-side, not at an arbitrary "typical" threshold.
const TYPICAL_WORDS = 3000;
const HARD_MAX_WORDS = 9000;

function wordCount(text: string): number {
  const trimmed = text.trim();
  return trimmed === "" ? 0 : trimmed.split(/\s+/).length;
}

export function NoteSubmitPage() {
  const [noteText, setNoteText] = useState("");
  const [pseudonym, setPseudonym] = useState("");
  const [visitDate, setVisitDate] = useState("");
  const [state, setState] = useState<SubmitState>("idle");
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const words = wordCount(noteText);
  const overTypical = words > TYPICAL_WORDS;
  const overHardLimit = words > HARD_MAX_WORDS;
  const canSubmit = noteText.trim().length > 0 && !overHardLimit && state !== "submitting";

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;

    setState("submitting");
    setError("");
    try {
      const result = await submitNote({
        note_text: noteText,
        pseudonym: pseudonym.trim() || null,
        visit_date: visitDate || null,
      });
      navigate(`/app/notes/${result.note.id}/analyses/${result.analysis.id}`);
    } catch (err) {
      setState("error");
      setError(err instanceof ApiError ? err.message : "Could not reach the server. Try again.");
    }
  }

  return (
    <div className="page">
      <p className="page-eyebrow">New encounter</p>
      <h1>Analyze a clinical note</h1>
      <p className="page-intro">
        Paste the note as written — the model reads it exactly as-is, no formatting required.
      </p>

      <div className="note-card">
        <div className="note-hint">
          <SparkleIcon />
          <span>
            You'll get conditions with quoted evidence, a documentation-quality flag per
            condition, suggested ICD-10 codes and any gaps a coder would flag — all editable
            before it's saved.
          </span>
        </div>

        <form onSubmit={handleSubmit} className="note-form">
          <div className="field-row">
            <div>
              <label htmlFor="pseudonym">Patient pseudonym (optional)</label>
              <input
                id="pseudonym"
                value={pseudonym}
                onChange={(e) => setPseudonym(e.target.value)}
                placeholder="e.g. P-014 — never a real identifier"
              />
            </div>
            <div>
              <label htmlFor="visitDate">Visit date (optional)</label>
              <input
                id="visitDate"
                type="date"
                value={visitDate}
                onChange={(e) => setVisitDate(e.target.value)}
              />
            </div>
          </div>

          <label htmlFor="noteText">Clinical note</label>
          <textarea
            id="noteText"
            rows={16}
            value={noteText}
            onChange={(e) => setNoteText(e.target.value)}
            placeholder="Paste the free-text clinical note here…"
            required
          />
          <div className={overHardLimit ? "word-count word-count-over" : "word-count"}>
            {words} words
            {overHardLimit
              ? " — too long to submit, trim it down"
              : overTypical
                ? " — longer than typical, but that's fine"
                : ""}
          </div>

          {state === "error" && <p className="form-error">{error}</p>}

          <button type="submit" disabled={!canSubmit}>
            {state === "submitting" ? "Analyzing… this can take a few seconds" : "Analyze note"}
          </button>
        </form>
      </div>
    </div>
  );
}
