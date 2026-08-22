import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getAnalysis, getNote, submitReview } from "../api/notes";
import type { AnalysisResponse, StoredAnalysisOutput, StoredCondition } from "../types/api";
import { AlertTriangleIcon, CheckCircleIcon, HistoryClockIcon, UnverifiedIcon } from "../components/icons";
import { buildHighlightedSegments } from "../utils/highlightNote";

type LoadState = "loading" | "loaded" | "error";
type SaveState = "idle" | "saving" | "saved" | "error";

function emptyCondition(): StoredCondition {
  return {
    name: "",
    evidence_quote: "",
    documentation_status: "ambiguous",
    status_reason: "",
    icd10_code: "",
    confidence: 0.5,
    quote_verified: false,
    source: "human_added",
    rejected: false,
  };
}

function sourceLabel(source: StoredCondition["source"]): string {
  if (source === "ai") return "AI";
  if (source === "human_edited") return "edited by you";
  return "added by you";
}

export function AnalysisPage() {
  const { noteId, analysisId } = useParams<{ noteId: string; analysisId: string }>();
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [noteText, setNoteText] = useState("");
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [loadError, setLoadError] = useState("");
  const [draft, setDraft] = useState<StoredAnalysisOutput | null>(null);
  const [saveState, setSaveState] = useState<SaveState>("idle");

  useEffect(() => {
    if (!noteId || !analysisId) return;
    let cancelled = false;
    setLoadState("loading");
    Promise.all([getAnalysis(noteId, analysisId), getNote(noteId)])
      .then(([analysisData, noteData]) => {
        if (cancelled) return;
        setAnalysis(analysisData);
        setDraft(analysisData.review ?? analysisData.ai_output);
        setNoteText(noteData.note_text);
        setLoadState("loaded");
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setLoadError(err instanceof Error ? err.message : "Failed to load analysis");
        setLoadState("error");
      });
    return () => {
      cancelled = true;
    };
  }, [noteId, analysisId]);

  function updateCondition(index: number, patch: Partial<StoredCondition>) {
    setDraft((prev) => {
      if (!prev) return prev;
      const conditions = prev.conditions.map((condition, i) => {
        if (i !== index) return condition;
        const nextSource = condition.source === "ai" ? "human_edited" : condition.source;
        return { ...condition, ...patch, source: nextSource };
      });
      return { ...prev, conditions };
    });
    setSaveState("idle");
  }

  function toggleReject(index: number) {
    setDraft((prev) => {
      if (!prev) return prev;
      const conditions = prev.conditions.map((condition, i) =>
        i === index ? { ...condition, rejected: !condition.rejected } : condition,
      );
      return { ...prev, conditions };
    });
    setSaveState("idle");
  }

  function addCondition() {
    setDraft((prev) => (prev ? { ...prev, conditions: [...prev.conditions, emptyCondition()] } : prev));
    setSaveState("idle");
  }

  async function saveReview() {
    if (!noteId || !analysisId || !draft) return;
    setSaveState("saving");
    try {
      const updated = await submitReview(noteId, analysisId, draft);
      setAnalysis(updated);
      setDraft(updated.review ?? updated.ai_output);
      setSaveState("saved");
    } catch {
      setSaveState("error");
    }
  }

  if (loadState === "loading") return <div className="page-loading">Loading analysis…</div>;

  if (loadState === "error" || !analysis) {
    return (
      <div className="page">
        <p className="form-error">{loadError}</p>
      </div>
    );
  }

  if (analysis.status === "failed") {
    return (
      <div className="page">
        <p className="page-eyebrow">Analysis</p>
        <h1>This one didn't come back clean</h1>
        <p className="form-error">
          {analysis.error_message ?? "The model could not produce a valid, schema-conforming result."}
        </p>
        <p className="muted" style={{ marginTop: 12 }}>
          Your note was saved even though the analysis failed — nothing was lost.
        </p>
      </div>
    );
  }

  if (!draft) return <div className="page">No analysis data available.</div>;

  return (
    <div className="page">
      <p className="page-eyebrow">Analysis</p>
      <h1>Review &amp; correct</h1>
      <p className="analysis-meta">
        <span>{analysis.model_version}</span>
        <span>·</span>
        <span>prompt {analysis.prompt_version}</span>
        <span>·</span>
        <span className={`status-pill status-${analysis.review_status}`}>{analysis.review_status}</span>
      </p>

      {analysis.recapture_reminders.length > 0 && (
        <div className="recapture-panel">
          <div className="recapture-panel-title">
            <HistoryClockIcon />
            Possible recapture gap{analysis.recapture_reminders.length > 1 ? "s" : ""}
          </div>
          <p className="recapture-panel-intro">
            Documented at a past visit for this patient, not mentioned today — chronic
            conditions have to be re-documented every visit or they stop counting toward
            risk adjustment.
          </p>
          <ul className="recapture-list">
            {analysis.recapture_reminders.map((reminder) => (
              <li key={reminder.condition_name} className="recapture-item">
                <span>
                  <strong>{reminder.condition_name}</strong> — last documented{" "}
                  {new Date(reminder.last_documented_at).toLocaleDateString()}
                </span>
                <Link to={`/app/notes/${reminder.last_note_id}/analyses/${reminder.last_analysis_id}`}>
                  View that visit →
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}

      <section>
        <h2>Original note</h2>
        <p className="page-intro" style={{ marginTop: -8, marginBottom: 14 }}>
          Evidence quotes highlighted in place — scan this instead of re-reading the whole note.
        </p>
        <div className="note-text-card">
          {buildHighlightedSegments(noteText, draft.conditions).map((segment, i) =>
            segment.status ? (
              <mark
                key={i}
                className={`note-highlight note-highlight-${segment.status}`}
                title={draft.conditions[segment.conditionIndex ?? 0]?.name}
              >
                {segment.text}
              </mark>
            ) : (
              <span key={i}>{segment.text}</span>
            ),
          )}
        </div>
      </section>

      <section>
        <h2>Summary</h2>
        <div className="summary-card">
          <textarea
            value={draft.summary}
            onChange={(e) => {
              setDraft((prev) => (prev ? { ...prev, summary: e.target.value } : prev));
              setSaveState("idle");
            }}
            rows={3}
          />
        </div>
      </section>

      <section>
        <h2>Conditions ({draft.conditions.length})</h2>
        {draft.conditions.map((condition, i) => (
          <div
            key={i}
            className={condition.rejected ? "condition-card condition-rejected" : "condition-card"}
            data-status={condition.documentation_status}
          >
            <div className="condition-header">
              <input
                className="condition-name"
                value={condition.name}
                onChange={(e) => updateCondition(i, { name: e.target.value })}
                placeholder="Condition name"
              />
              <span className={`source-badge source-${condition.source}`}>{sourceLabel(condition.source)}</span>
              {!condition.quote_verified && (
                <span className="unverified-badge" title="This quote could not be matched verbatim in the note">
                  <UnverifiedIcon /> unverified quote
                </span>
              )}
            </div>

            <label>Evidence quote</label>
            <textarea
              value={condition.evidence_quote}
              onChange={(e) => updateCondition(i, { evidence_quote: e.target.value })}
              rows={2}
            />

            <div className="field-row field-row-triple">
              <div>
                <label>Documentation status</label>
                <select
                  value={condition.documentation_status}
                  onChange={(e) =>
                    updateCondition(i, {
                      documentation_status: e.target.value as StoredCondition["documentation_status"],
                    })
                  }
                >
                  <option value="well_documented">Well documented</option>
                  <option value="ambiguous">Ambiguous</option>
                  <option value="mentioned_without_assessment_or_plan">Mentioned, no assessment/plan</option>
                </select>
                <p className="status-reason">{condition.status_reason}</p>
              </div>
              <div>
                <label>ICD-10 code</label>
                <input value={condition.icd10_code} onChange={(e) => updateCondition(i, { icd10_code: e.target.value })} />
              </div>
              <div>
                <label>Confidence</label>
                <input
                  type="number"
                  min={0}
                  max={1}
                  step={0.05}
                  value={condition.confidence}
                  onChange={(e) => updateCondition(i, { confidence: Number(e.target.value) })}
                />
              </div>
            </div>

            <button type="button" className="link-button" onClick={() => toggleReject(i)}>
              {condition.rejected ? "Un-reject" : "Reject this condition"}
            </button>
          </div>
        ))}
        <button type="button" onClick={addCondition}>
          + Add a condition the model missed
        </button>
      </section>

      <section>
        <h2>Documentation gaps</h2>
        {draft.documentation_gaps.length === 0 ? (
          <p className="muted">No gaps flagged.</p>
        ) : (
          <ul className="gap-list">
            {draft.documentation_gaps.map((gap, i) => (
              <li className="gap-item" key={i}>
                <AlertTriangleIcon />
                <span>{gap}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <div className="save-bar">
        <button type="button" onClick={saveReview} disabled={saveState === "saving"}>
          {saveState === "saving" ? "Saving…" : "Save review"}
        </button>
        {saveState === "saved" && (
          <span className="save-confirmation">
            <CheckCircleIcon /> Saved
          </span>
        )}
        {saveState === "error" && <span className="form-error">Could not save. Try again.</span>}
      </div>

      {analysis.ai_output && (
        <details className="original-ai-output">
          <summary>View original AI output (unedited, preserved permanently)</summary>
          <pre>{JSON.stringify(analysis.ai_output, null, 2)}</pre>
        </details>
      )}
    </div>
  );
}
