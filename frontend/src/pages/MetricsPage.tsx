import { useEffect, useState } from "react";
import { getMetrics } from "../api/notes";
import type { ReviewMetrics } from "../types/api";
import { MetricsIcon } from "../components/icons";

type LoadState = "loading" | "loaded" | "error";

function formatPercent(rate: number): string {
  return `${Math.round(rate * 100)}%`;
}

export function MetricsPage() {
  const [metrics, setMetrics] = useState<ReviewMetrics | null>(null);
  const [state, setState] = useState<LoadState>("loading");

  useEffect(() => {
    let cancelled = false;
    getMetrics()
      .then((data) => {
        if (cancelled) return;
        setMetrics(data);
        setState("loaded");
      })
      .catch(() => {
        if (!cancelled) setState("error");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (state === "loading") return <div className="page-loading">Loading metrics…</div>;

  if (state === "error" || !metrics) {
    return (
      <div className="page">
        <p className="form-error">Could not load metrics. Try reloading the page.</p>
      </div>
    );
  }

  return (
    <div className="page">
      <p className="page-eyebrow">Trust, measured</p>
      <h1>How often the AI needed correcting</h1>
      <p className="page-intro">
        Every edit, rejection, and addition you've ever made, aggregated — this is the dataset
        the assessment calls "the single most valuable thing this product will ever produce."
      </p>

      {metrics.reviewed_analyses === 0 ? (
        <div className="empty-state">
          <MetricsIcon size={28} />
          <p style={{ marginTop: 12 }}>No reviewed notes yet — metrics fill in as you review analyses.</p>
        </div>
      ) : (
        <>
          <div className="metrics-summary">
            <div className="metrics-stat">
              <div className="metrics-stat-num">{metrics.reviewed_analyses}</div>
              <div className="metrics-stat-label">Reviewed notes</div>
            </div>
            <div className="metrics-stat">
              <div className="metrics-stat-num">{formatPercent(metrics.correction_rate)}</div>
              <div className="metrics-stat-label">Correction rate</div>
            </div>
            <div className="metrics-stat">
              <div className="metrics-stat-num">{metrics.total_conditions_suggested}</div>
              <div className="metrics-stat-label">AI-suggested conditions</div>
            </div>
            <div className="metrics-stat">
              <div className="metrics-stat-num">{metrics.total_edited}</div>
              <div className="metrics-stat-label">Edited</div>
            </div>
            <div className="metrics-stat">
              <div className="metrics-stat-num">{metrics.total_rejected}</div>
              <div className="metrics-stat-label">Rejected</div>
            </div>
            <div className="metrics-stat">
              <div className="metrics-stat-num">{metrics.total_added}</div>
              <div className="metrics-stat-label">Added by you</div>
            </div>
          </div>

          <h2>Broken down by condition</h2>
          <table className="history-table">
            <thead>
              <tr>
                <th>Condition</th>
                <th>Suggested</th>
                <th>Edited</th>
                <th>Rejected</th>
                <th>Added by you</th>
              </tr>
            </thead>
            <tbody>
              {metrics.by_condition.map((row) => (
                <tr key={row.name}>
                  <td>{row.name}</td>
                  <td>{row.times_suggested}</td>
                  <td>{row.times_edited}</td>
                  <td>{row.times_rejected}</td>
                  <td>{row.times_added}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}
