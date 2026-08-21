import { useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { BrandGlyph, CheckCircleIcon, GoogleIcon } from "../components/icons";

type Mode = "signin" | "signup";
type SubmitState = "idle" | "submitting" | "error";

const FEATURES = [
  "Structured conditions, evidence and ICD-10 suggestions in seconds",
  "Every quote verified against your original note text",
  "Your corrections are saved — the model's draft never disappears",
];

export function AuthPage() {
  const [mode, setMode] = useState<Mode>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [state, setState] = useState<SubmitState>("idle");
  const [errorMessage, setErrorMessage] = useState("");
  const { signIn, signUp, signInWithGoogle } = useAuth();
  const navigate = useNavigate();

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setState("submitting");
    setErrorMessage("");
    try {
      if (mode === "signup") {
        await signUp(email, password);
      } else {
        await signIn(email, password);
      }
      navigate("/app", { replace: true });
    } catch (err) {
      setState("error");
      setErrorMessage(err instanceof Error ? err.message : "Something went wrong");
    }
  }

  async function handleGoogleSignIn() {
    setState("submitting");
    setErrorMessage("");
    try {
      await signInWithGoogle();
      navigate("/app", { replace: true });
    } catch (err) {
      setState("error");
      setErrorMessage(err instanceof Error ? err.message : "Google sign-in failed");
    }
  }

  return (
    <div className="auth-shell">
      <div className="auth-hero">
        <div className="auth-hero-content">
          <div className="auth-hero-brand">
            <span className="sidebar-brand-mark">
              <BrandGlyph />
            </span>
            <span>Note Insight</span>
          </div>

          <h1>Turn a visit note into a coder-ready analysis before you forget the patient.</h1>
          <p>
            Paste a free-text clinical note and get structured conditions, documentation gaps and
            suggested codes back in under a minute — a draft to correct, never an authority.
          </p>

          <div className="auth-hero-features">
            {FEATURES.map((feature) => (
              <div className="auth-hero-feature" key={feature}>
                <CheckCircleIcon size={16} />
                <span>{feature}</span>
              </div>
            ))}
          </div>
        </div>
        <p className="auth-hero-foot">Built for DoctusTech · synthetic data only</p>
      </div>

      <div className="auth-panel">
        <div className="auth-card">
          <h1>{mode === "signin" ? "Welcome back" : "Create your account"}</h1>
          <p className="auth-subtitle">
            {mode === "signin" ? "Sign in to continue" : "A few seconds, no card required"}
          </p>
          <form onSubmit={handleSubmit}>
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
            />
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              required
              minLength={6}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === "signup" ? "new-password" : "current-password"}
            />
            {state === "error" && <p className="form-error">{errorMessage}</p>}
            <button type="submit" disabled={state === "submitting"}>
              {state === "submitting" ? "Please wait…" : mode === "signin" ? "Sign in" : "Sign up"}
            </button>
          </form>

          <div className="auth-divider">
            <span>or</span>
          </div>

          <button
            type="button"
            className="google-button"
            onClick={handleGoogleSignIn}
            disabled={state === "submitting"}
          >
            <GoogleIcon />
            Continue with Google
          </button>

          <button
            type="button"
            className="link-button"
            onClick={() => setMode(mode === "signin" ? "signup" : "signin")}
          >
            {mode === "signin" ? "Need an account? Sign up" : "Already have an account? Sign in"}
          </button>
        </div>
      </div>
    </div>
  );
}
