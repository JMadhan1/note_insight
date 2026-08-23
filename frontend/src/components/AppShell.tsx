import { useEffect, useState } from "react";
import { NavLink, Navigate, Outlet } from "react-router-dom";
import { listNotes } from "../api/notes";
import { useAuth } from "../context/AuthContext";
import { BrandGlyph, HistoryIcon, MetricsIcon, NewNoteIcon } from "./icons";

function navLinkClass({ isActive }: { isActive: boolean }): string {
  return isActive ? "sidebar-link active" : "sidebar-link";
}

interface WorkspaceStats {
  total: number;
  pending: number;
}

/** Real counts pulled from the note list, not decoration — used to fill the sidebar
 * with something the clinician actually cares about (how many notes are waiting on
 * their review) rather than empty vertical space. */
function useWorkspaceStats(): WorkspaceStats | null {
  const [stats, setStats] = useState<WorkspaceStats | null>(null);

  useEffect(() => {
    let cancelled = false;
    listNotes()
      .then((notes) => {
        if (cancelled) return;
        setStats({
          total: notes.length,
          pending: notes.filter((n) => n.review_status === "pending").length,
        });
      })
      .catch(() => {
        if (!cancelled) setStats(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return stats;
}

export function AppShell() {
  const { user, loading, signOut } = useAuth();
  const stats = useWorkspaceStats();

  if (loading) {
    return <div className="page-loading">Loading…</div>;
  }
  if (!user) {
    return <Navigate to="/login" replace />;
  }

  const initial = (user.email ?? "?").charAt(0).toUpperCase();

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <span className="sidebar-brand-mark">
            <BrandGlyph />
          </span>
          <span className="sidebar-brand-word">Note Insight</span>
        </div>

        <span className="sidebar-section-label">Workspace</span>
        <nav className="sidebar-nav">
          <NavLink to="/app" end className={navLinkClass}>
            <NewNoteIcon /> New note
          </NavLink>
          <NavLink to="/app/history" className={navLinkClass}>
            <HistoryIcon /> History
          </NavLink>
          <NavLink to="/app/metrics" className={navLinkClass}>
            <MetricsIcon /> Metrics
          </NavLink>
        </nav>

        {stats && stats.total > 0 && (
          <div className="sidebar-stats" aria-label="Workspace summary">
            <div className="sidebar-stat">
              <span className="sidebar-stat-value">{stats.total}</span>
              <span className="sidebar-stat-label">Notes analyzed</span>
            </div>
            <div className="sidebar-stat">
              <span className="sidebar-stat-value sidebar-stat-value-pending">{stats.pending}</span>
              <span className="sidebar-stat-label">Awaiting review</span>
            </div>
          </div>
        )}

        <div className="sidebar-spacer" />

        <div className="sidebar-footer">
          <div className="sidebar-user">
            <span className="user-avatar">{initial}</span>
            <span className="user-email">{user.email}</span>
          </div>
          <button type="button" className="sidebar-signout" onClick={() => void signOut()}>
            Sign out
          </button>
        </div>
      </aside>

      <main className="main-area">
        <Outlet />
      </main>
    </div>
  );
}
