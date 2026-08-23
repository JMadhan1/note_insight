import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { BrandGlyph, CheckCircleIcon, HistoryIcon, SparkleIcon } from "../components/icons";

const PRINCIPLES = [
  {
    tag: "STRUCTURE",
    icon: SparkleIcon,
    title: "Structured in seconds",
    body: "Conditions, evidence, documentation status and suggested ICD-10 codes — returned as schema-validated data, not prose you have to parse yourself.",
  },
  {
    tag: "VERIFY",
    icon: CheckCircleIcon,
    title: "Every quote checked",
    body: "Each piece of evidence is verified as a literal excerpt from your note. Anything the model can't verify is flagged, not hidden.",
  },
  {
    tag: "REVIEW",
    icon: HistoryIcon,
    title: "Your corrections, preserved",
    body: "Edit, reject, or add conditions — the model's original draft is never overwritten, only layered under your review.",
  },
];

export function LandingPage() {
  const { user } = useAuth();
  const primaryHref = user ? "/app" : "/login";
  const primaryLabel = user ? "Go to your notes" : "Get started";

  return (
    <div className="landing">
      <nav className="landing-nav">
        <div className="landing-brand">
          <span className="sidebar-brand-mark">
            <BrandGlyph />
          </span>
          <span className="landing-brand-word">Note Insight</span>
        </div>
        <Link to={primaryHref} className="landing-nav-cta">
          {user ? "Go to app" : "Sign in"}
        </Link>
      </nav>

      <header className="landing-hero">
        <div className="landing-hero-copy">
          <span className="landing-kicker">Note Insight — AI-assisted coding review</span>
          <h1 className="landing-title">
            Turn a visit note into a<br />
            coder-ready analysis <em>before you forget the patient.</em>
          </h1>
          <p className="landing-sub">
            Paste a free-text clinical note and get structured conditions, documentation gaps,
            and suggested codes back in under a minute — a draft to correct, never an authority.
          </p>
          <div className="landing-cta-row">
            <Link to={primaryHref} className="cta-primary">
              {primaryLabel}
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                <path d="M5 12h14M13 6l6 6-6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </Link>
            {!user && (
              <Link to="/login" className="cta-secondary">
                I already have an account
              </Link>
            )}
          </div>
        </div>

        <div className="chart-card">
          <div className="chart-card-head">
            <span className="chart-card-tab">Exhibit — visit note</span>
            <span className="chart-card-date">Today, 09:14</span>
          </div>
          <p className="chart-note-text">
            Patient presents today for follow-up of{" "}
            <mark className="chart-mark chart-mark-teal">type 2 diabetes, on metformin</mark>.
            Blood pressure was{" "}
            <mark className="chart-mark chart-mark-amber">a little high today, 148/92</mark>.
            Will recheck at next visit.
          </p>
          <div className="chart-annotations">
            <div className="chart-annotation">
              <span className="chart-annotation-dot chart-annotation-dot-teal" />
              Verified quote · well documented · <code>E11.9</code>
            </div>
            <div className="chart-annotation">
              <span className="chart-annotation-dot chart-annotation-dot-amber" />
              Ambiguous — no formal diagnosis or treatment plan stated
            </div>
          </div>
        </div>
      </header>

      <section className="landing-principles">
        {PRINCIPLES.map((p) => (
          <div className="landing-principle" key={p.title}>
            <span className="landing-principle-tag">{p.tag}</span>
            <h3>{p.title}</h3>
            <p>{p.body}</p>
          </div>
        ))}
      </section>

      <section className="landing-file-banner">
        <span className="landing-file-tab">Exhibit A — source</span>
        <div className="landing-file-body">
          <div className="landing-file-text">
            <h3>Curious how this actually works?</h3>
            <p>Full source, data model, and design decisions are documented in the repo.</p>
          </div>
          <a
            className="landing-repo-cta"
            href="https://github.com/JMadhan1/note_insight"
            target="_blank"
            rel="noopener"
          >
            <svg width="17" height="17" viewBox="0 0 16 16" fill="currentColor">
              <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8Z" />
            </svg>
            View source on GitHub
          </a>
        </div>
      </section>

      <footer className="landing-foot">
        <div className="landing-foot-author">
          <span className="user-avatar" aria-hidden="true">M</span>
          <div className="landing-foot-author-text">
            <strong>Built by Madhan J</strong>
            <span>Full-Stack / AI Engineer candidate</span>
          </div>
        </div>
        <div className="landing-foot-links">
          <a href="https://github.com/JMadhan1" target="_blank" rel="noopener">GitHub</a>
          <a href="https://www.linkedin.com/in/jmadhan/" target="_blank" rel="noopener">LinkedIn</a>
          <a href="https://jmadhan.me/" target="_blank" rel="noopener">Portfolio</a>
        </div>
      </footer>
    </div>
  );
}
