import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { getAnalysis, submitReview } from "../api/notes";
import type { AnalysisResponse, StoredAnalysisOutput, StoredCondition } from "../types/api";

type LoadState = "loading" | "loaded" | "error";
type SaveState = "idle" | "saving" | "saved" | "error";

function emptyCondition(): StoredCondition {
  return {
    name: "",
    evidence_quote: "",
    documentation_status: "ambiguous",
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
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [loadError, setLoadError] = useState("");
  const [draft, setDraft] = useState<StoredAnalysisOutput | null>(null);
  const [saveState, setSaveState] = useState<SaveState>("idle");

  useEffect(() => {
    if (!noteId || !analysisId) return;
    let cancelled = false;
    setLoadState("loading");
    getAnalysis(noteId, analysisId)
      .then((data) => {
        if (cancelled) return;
        setAnalysis(data);
        setDraft(data.review ?? data.ai_output);
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

  if (loadState === "loading") return <div className="page">Loading analysis…</div>;

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
        <h1>Analysis failed</h1>
        <p className="form-error">
          {analysis.error_message ?? "The model could not produce a valid, schema-conforming result."}
        </p>
        <p>Your note was saved even though the analysis failed — nothing was lost.</p>
      </div>
    );
  }

  if (!draft) return <div className="page">No analysis data available.</div>;

  return (
    <div className="page">
      <h1>Analysis</h1>
      <p className="meta-line">
        Model: {analysis.model_version} · Prompt: {analysis.prompt_version} ·{" "}
        {analysis.review_status === "reviewed" ? "Reviewed" : "Pending review"}
      </p>

      <section>
        <h2>Summary</h2>
        <textarea
          value={draft.summary}
          onChange={(e) => {
            setDraft((prev) => (prev ? { ...prev, summary: e.target.value } : prev));
            setSaveState("idle");
          }}
          rows={3}
        />
      </section>

      <section>
        <h2>Conditions ({draft.conditions.length})</h2>
        {draft.conditions.map((condition, i) => (
          <div
            key={i}
            className={condition.rejected ? "condition-card condition-rejected" : "condition-card"}
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
                  unverified quote
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
          <ul>
            {draft.documentation_gaps.map((gap, i) => (
              <li key={i}>{gap}</li>
            ))}
          </ul>
        )}
      </section>

      <div className="save-bar">
        <button type="button" onClick={saveReview} disabled={saveState === "saving"}>
          {saveState === "saving" ? "Saving…" : "Save review"}
        </button>
        {saveState === "saved" && <span className="save-confirmation">Saved</span>}
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
