import { useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { submitNote } from "../api/notes";
import { ApiError } from "../api/client";

type SubmitState = "idle" | "submitting" | "error";

const MAX_WORDS = 3000;

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
  const overLimit = words > MAX_WORDS;
  const canSubmit = noteText.trim().length > 0 && !overLimit && state !== "submitting";

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
      navigate(`/notes/${result.note.id}/analyses/${result.analysis.id}`);
    } catch (err) {
      setState("error");
      setError(err instanceof ApiError ? err.message : "Could not reach the server. Try again.");
    }
  }

  return (
    <div className="page">
      <h1>New note</h1>
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
        <div className={overLimit ? "word-count word-count-over" : "word-count"}>
          {words} words{overLimit ? " — over the 3000 word limit" : ""}
        </div>

        {state === "error" && <p className="form-error">{error}</p>}

        <button type="submit" disabled={!canSubmit}>
          {state === "submitting" ? "Analyzing… this can take a few seconds" : "Analyze note"}
        </button>
      </form>
    </div>
  );
}
