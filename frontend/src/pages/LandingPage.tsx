import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { BrandGlyph, CheckCircleIcon, HistoryIcon, SparkleIcon, UnverifiedIcon } from "../components/icons";

const FEATURES = [
  {
    icon: SparkleIcon,
    title: "Structured in seconds",
    body: "Conditions, evidence, documentation status and suggested ICD-10 codes — returned as schema-validated data, not prose you have to parse yourself.",
  },
  {
    icon: CheckCircleIcon,
    title: "Every quote checked",
    body: "Each piece of evidence is verified as a literal excerpt from your note. Anything the model can't verify is flagged, not hidden.",
  },
  {
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
          <span className="landing-eyebrow">
            <span className="dot" /> AI-assisted clinical documentation
          </span>
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

        <div className="landing-preview">
          <div className="landing-preview-window">
            <div className="landing-preview-titlebar">
              <span /><span /><span />
              <span className="landing-preview-url">note-insight · analysis</span>
            </div>
            <div className="landing-preview-body">
              <div className="condition-card" data-status="well_documented" style={{ marginBottom: 10 }}>
                <div className="condition-header">
                  <strong style={{ fontFamily: "var(--font-display)", fontSize: 15 }}>
                    Type 2 Diabetes Mellitus
                  </strong>
                  <span className="source-badge source-ai">AI</span>
                </div>
                <p className="landing-preview-quote">&ldquo;has diabetes, on metformin&rdquo;</p>
              </div>
              <div className="condition-card" data-status="ambiguous" style={{ marginBottom: 0 }}>
                <div className="condition-header">
                  <strong style={{ fontFamily: "var(--font-display)", fontSize: 15 }}>
                    Elevated Blood Pressure
                  </strong>
                  <span className="unverified-badge">
                    <UnverifiedIcon /> unverified
                  </span>
                </div>
                <p className="landing-preview-quote">&ldquo;BP was a little high today, 148/92&rdquo;</p>
              </div>
              <div className="landing-preview-gap">
                → Diabetes documented without type or control status
              </div>
            </div>
          </div>
        </div>
      </header>

      <section className="landing-features">
        {FEATURES.map((feature) => (
          <div className="landing-feature" key={feature.title}>
            <span className="landing-feature-icon">
              <feature.icon size={20} />
            </span>
            <h3>{feature.title}</h3>
            <p>{feature.body}</p>
          </div>
        ))}
      </section>

      <footer className="landing-foot">
        <span>Built for synthetic clinical notes only — never real patient data.</span>
        <Link to={primaryHref}>{primaryLabel} →</Link>
      </footer>
    </div>
  );
}
