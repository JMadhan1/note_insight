import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listNotes } from "../api/notes";
import type { NoteListItem } from "../types/api";
import { HistoryIcon } from "../components/icons";

type LoadState = "loading" | "loaded" | "error";

export function HistoryPage() {
  const [notes, setNotes] = useState<NoteListItem[]>([]);
  const [state, setState] = useState<LoadState>("loading");

  useEffect(() => {
    let cancelled = false;
    listNotes()
      .then((data) => {
        if (cancelled) return;
        setNotes(data);
        setState("loaded");
      })
      .catch(() => {
        if (!cancelled) setState("error");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (state === "loading") return <div className="page-loading">Loading history…</div>;

  if (state === "error") {
    return (
      <div className="page">
        <p className="form-error">Could not load your notes. Try reloading the page.</p>
      </div>
    );
  }

  return (
    <div className="page">
      <p className="page-eyebrow">Your notes</p>
      <h1>History</h1>
      <p className="page-intro">Every note you've analyzed, newest first, with your review status.</p>

      {notes.length === 0 ? (
        <div className="empty-state">
          <HistoryIcon size={28} />
          <p style={{ marginTop: 12 }}>
            No notes analyzed yet. <Link to="/app">Analyze your first note</Link>.
          </p>
        </div>
      ) : (
        <table className="history-table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Pseudonym</th>
              <th>Conditions</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {notes.map((note) => (
              <tr key={note.id}>
                <td>
                  {note.latest_analysis_id ? (
                    <Link to={`/app/notes/${note.id}/analyses/${note.latest_analysis_id}`}>
                      {new Date(note.created_at).toLocaleString()}
                    </Link>
                  ) : (
                    new Date(note.created_at).toLocaleString()
                  )}
                </td>
                <td>{note.pseudonym ?? "—"}</td>
                <td>{note.condition_count}</td>
                <td>
                  <span className={`status-pill status-${note.review_status}`}>{note.review_status}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
