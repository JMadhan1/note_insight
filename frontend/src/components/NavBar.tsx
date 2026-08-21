import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export function NavBar() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();

  if (!user) return null;

  async function handleSignOut() {
    await signOut();
    navigate("/login", { replace: true });
  }

  return (
    <nav className="navbar">
      <Link to="/" className="navbar-brand">
        Note Insight
      </Link>
      <div className="navbar-links">
        <Link to="/">New note</Link>
        <Link to="/history">History</Link>
        <span className="navbar-user">{user.email}</span>
        <button type="button" className="link-button" onClick={handleSignOut}>
          Sign out
        </button>
      </div>
    </nav>
  );
}
