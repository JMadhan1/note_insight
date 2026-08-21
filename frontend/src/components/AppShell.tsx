import { NavLink, Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { BrandGlyph, HistoryIcon, NewNoteIcon } from "./icons";

function navLinkClass({ isActive }: { isActive: boolean }): string {
  return isActive ? "sidebar-link active" : "sidebar-link";
}

export function AppShell() {
  const { user, loading, signOut } = useAuth();

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

        <nav className="sidebar-nav">
          <NavLink to="/app" end className={navLinkClass}>
            <NewNoteIcon /> New note
          </NavLink>
          <NavLink to="/app/history" className={navLinkClass}>
            <HistoryIcon /> History
          </NavLink>
        </nav>

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
