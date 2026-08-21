import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listNotes } from "../api/notes";
import type { NoteListItem } from "../types/api";

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

  if (state === "loading") return <div className="page">Loading history…</div>;

  if (state === "error") {
    return (
      <div className="page">
        <p className="form-error">Could not load your notes. Try reloading the page.</p>
      </div>
    );
  }

  if (notes.length === 0) {
    return (
      <div className="page">
        <h1>History</h1>
        <p>
          No notes analyzed yet. <Link to="/">Analyze your first note</Link>.
        </p>
      </div>
    );
  }

  return (
    <div className="page">
      <h1>History</h1>
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
                  <Link to={`/notes/${note.id}/analyses/${note.latest_analysis_id}`}>
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
    </div>
  );
}
