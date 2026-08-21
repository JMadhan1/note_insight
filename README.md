# Note Insight

A tool that turns a clinician's free-text visit note into a structured, schema-validated
analysis (conditions, evidence, documentation gaps, suggested ICD-10 codes) within seconds,
with every AI extraction traceable back to the source text and every human correction
preserved alongside the model's original output.

Built for the DoctusTech Junior Full-Stack / AI Engineer technical assessment. See
[PROJECT_PLAN.md](PROJECT_PLAN.md) for the phase-by-phase build plan this repo followed.

---

## Contents

- [How to run it locally](#how-to-run-it-locally)
- [Data model](#data-model)
- [Design decisions](#design-decisions)
- [What I'd build next / what's left unfinished](#whatd-i-build-next--whats-left-unfinished)
- [Deployment](#deployment)
- [Prompt](#prompt)
- [Sample notes](#sample-notes)
- [Time spent](#time-spent)

---

## How to run it locally

Requires Node.js 20+, Python 3.11+, and a Firebase project (free Spark plan — no card
required) with **Authentication** (email/password provider enabled) and **Firestore**
(production mode) turned on, plus a **Gemini API key** from
[aistudio.google.com/apikey](https://aistudio.google.com/apikey).

### 1. Backend

```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate   # Windows Git Bash; use .venv\Scripts\activate on cmd/PowerShell
pip install -r requirements.txt

cp .env.example .env
# Edit .env: paste your GEMINI_API_KEY

# Firebase console > Project settings > Service accounts > Generate new private key
# Save the downloaded file as backend/serviceAccountKey.json (gitignored, never commit it)

uvicorn app.main:app --reload --port 8000
```

Visit `http://localhost:8000/health` — should return `{"status": "ok"}`. This works even
before the Gemini key or Firebase service account are in place; both are only required the
moment a route that actually needs them is called (`/notes` needs both, `/health` needs
neither) — see [Design decisions](#design-decisions).

Run the test suite:

```bash
cd backend
pytest
```

### 2. Frontend

```bash
cd frontend
npm install

cp .env.example .env
# Firebase console > Project settings > General > Your apps > Web app > SDK config
# Paste each value into .env

npm run dev
```

Visit `http://localhost:5173`. Sign up with any email/password (Firebase Auth handles this —
no separate backend user table).

---

## Data model

Firestore, chosen over Postgres/SQLite for three reasons: it needs no card on the free
(Spark) plan, it shares one credential/SDK surface with Firebase Auth (the same project, the
same UID space), and its collection-per-parent query model maps directly onto "all notes for
user X, newest first" — see below. The tradeoff is less flexible ad-hoc querying than SQL,
which doesn't matter here since every query this product needs is "one user's notes, or one
note's analyses."

Four distinct entities — deliberately not collapsed into one document, per the assessment's
own warning that doing so "will cause you problems by day three":

```
Firebase Auth user (uid)          — not a Firestore document; Firestore paths are keyed by it
  └── users/{uid}/notes/{noteId}                              — what the clinician pasted, immutable
        └── .../notes/{noteId}/analyses/{analysisId}          — one per LLM run
              ├── aiOutput   — frozen the moment Gemini responds; never edited again
              └── review     — the human-corrected version, layered on top; null until reviewed
```

**Why subcollections, not a flat "one analysis per note" document**: this directly answers the
assessment's own test question — "what happens when the same note is analyzed twice, e.g.
after you improve your prompt?" Each re-analysis is a new sibling document under the same
note. Nothing is overwritten and nothing disappears; the note's `latestAnalysisId` field just
points the UI at the newest one, while older analyses stay individually queryable (each
carries its own `promptVersion` and `modelVersion`, so a specific run is always attributable
to the prompt/model that produced it).

**Why `aiOutput` and `review` are two separate objects, not one mutable object with a
per-field "edited" flag**: the assessment calls the model-vs-human diff "the single most
valuable dataset the product will ever produce." That diff has to be reconstructable forever,
which means the original can never be overwritten in place — only shadowed by a second object.
`GET /notes/{id}/analyses/{id}` always returns both; the frontend shows the human-editable
version with per-condition badges (`AI` / `edited by you` / `added by you`) and keeps the raw
original visible in a collapsible panel.

**Which fields are written by which layer**:

| Field | Written by |
|---|---|
| `noteText`, `pseudonym`, `visitDate` | Human (the clinician, at submission) |
| `aiOutput` | Machine (Gemini, via the backend) — never touched again after creation |
| `review` | Human (the clinician, during review) |
| `quoteVerified` (per condition) | System — computed by the backend's substring-verification pass, not trusted from either the model or the client |
| `latestAnalysisId`, `latestConditionCount`, `latestReviewStatus` | System — denormalized onto the note doc by the backend whenever an analysis completes or is reviewed |

**The query that matters — "all notes for user X, newest first"**: `users/{uid}/notes`
ordered by `createdAt desc`. Because it's a subcollection keyed by `{uid}`, and every read in
`backend/app/firestore_service.py` takes `uid` as its first argument sourced only from the
verified Firebase ID token (never from a client-supplied field — see `app/auth.py`), a request
authenticated as user A cannot reach user B's data by guessing a note or analysis id: the path
itself is rooted at the caller's own uid. This is checked structurally in
`backend/tests/test_firestore_isolation.py`, not just asserted in prose. It's a single-field
`order_by` with no additional filter, so it needs no composite index — Firestore's automatic
per-field index covers it. `condition_count` and `review_status` are denormalized onto the
note document (updated whenever an analysis completes or is reviewed) specifically so the
history list is one query, not an N+1 fetch into each note's `analyses` subcollection.

One clarification versus the plan in `PROJECT_PLAN.md`: Firestore is only ever touched
server-side, through the Admin SDK with a service account — the frontend talks to the FastAPI
backend, never to Firestore directly. That's necessary anyway since the Gemini key and the
orchestration logic have to live server-side. It means Firestore *security rules* aren't the
enforcement layer here (the Admin SDK bypasses them); the enforcement is the uid-scoped path
construction described above, gated by server-side ID token verification.

---

## Design decisions

**1. Gemini's native `response_schema` instead of prompting for JSON and parsing it.**
`google-genai`'s `GenerateContentConfig(response_mime_type="application/json",
response_schema=AIAnalysisOutput)` constrains the model's output at generation time and hands
back an object already validated against the Pydantic model (`response.parsed`). The
alternative — asking nicely for JSON in the prompt and regex/string-splitting the reply — is
exactly what the assessment says will be marked down, and in practice it's also just less
reliable. The cost is being tied to a Gemini SDK feature; if a second provider were added
later (Claude, GPT), the schema and the verification/retry logic in `gemini_service.py` would
carry over unchanged, only the API call itself would need a provider-specific adapter.

**2. Retry once on schema-invalid output, then fail explicitly rather than looping or
guessing.** `run_analysis()` in `backend/app/gemini_service.py` gives the model one more
attempt with an explicit "your last response didn't match the schema" follow-up, then raises
`AnalysisFailure`. The alternative was either silently retrying indefinitely (masks a
systemic prompt problem behind latency) or failing on the first bad response (throws away a
cheap, often-successful second attempt). The route handler (`routers/notes.py`) then stores a
`status: "failed"` analysis with the error preserved, rather than losing the note — the
clinician's note is never dropped just because the model had a bad response.

**3. Normalized substring matching to verify evidence quotes, surfaced rather than hidden.**
`verify_quote()` lowercases, collapses whitespace, and strips punctuation before checking that
a claimed quote is a literal substring of the note — tolerant of trivial formatting
differences, strict about actual content. A condition whose quote fails this check is not
discarded (that would silently hide a possibly-real finding); it's kept and flagged
`quote_verified: false`, shown in the UI as "unverified quote" so the clinician's attention
goes exactly where the model's claim is weakest. This is the concrete answer to "how do you
know the model didn't make this up?" — tested in `test_quote_verification.py` and
`test_gemini_service.py`, including a deliberate false-positive check (`"diabetes"` must not
match `"diabetic"`).

**4. Cloud Run over Fly.io/Railway for the backend, despite the assessment listing all four
options.** Both Fly.io and Railway's genuinely free tiers are gone as of 2026 — Fly.io removed
free allowances for new accounts in 2024, and Railway's "free" plan is now a one-time $5
credit that expires in 30 days, not durable hosting. Cloud Run's always-free quota (2M
requests/month) has no such expiry and shares a GCP project with Firebase. The tradeoff is a
billing account has to exist on the account (even though nothing is charged under quota),
versus Render, which needs no card at all but sleeps the container after 15 minutes idle
(30–60s cold start on the next request) — a reasonable fallback if avoiding the billing-account
step matters more than avoiding cold starts.

**5. Lazy secret validation instead of required environment variables at startup.**
`Settings.gemini_api_key` and the Firebase service-account path both default to empty/unset
rather than being required fields — `app/config.py` and `app/auth.py` only raise once a route
that actually needs the secret is called. This was a practical necessity while building ahead
of receiving real credentials (the app, `/health`, and 20+ tests all had to run without them),
but it also means a misconfigured deploy fails on `/notes`, not by refusing to boot at all —
worth knowing if `/health` ever looks fine while nothing else works.

**6. Firestore uses explicit service-account credentials, not `google.auth.default()`.**
`firestore.Client()` with no arguments relies on Application Default Credentials, which only
exist automatically on GCP infrastructure (or after `gcloud auth application-default login`
locally) — running it as-written against a real project surfaced this immediately as a
`DefaultCredentialsError`. `firestore_service.get_db()` now builds credentials explicitly from
the same service-account file already required for Firebase Admin
(`google.oauth2.service_account.Credentials.from_service_account_file(...)`), so there's one
secret to configure locally, not two, and no assumption that the app is running somewhere with
ADC pre-wired.

---

## What'd I build next / what's left unfinished

Left unfinished, deliberately, in favor of getting the core loop solid end to end:

- **No automated frontend tests.** Backend has 23 tests covering schema validation, quote
  verification, the Gemini retry/failure path, and uid-scoped data isolation; the frontend has
  none. Given more time, component tests for `AnalysisPage`'s review-diff logic (the
  `source: ai → human_edited` transition) would be the highest-value addition.
- **No re-analysis flow in the UI.** The data model supports multiple analyses per note (see
  above) and the backend has no obstacle to a "re-analyze with the current prompt" button, but
  no route or UI exists for triggering it yet — a note can only be analyzed once from the
  current frontend.
- **No streaming, caching, or rate limiting** (all listed as optional bonuses in the
  assessment). Caching identical notes would be cheap to add on top of the existing analysis
  pipeline; rate limiting per uid would sit naturally as FastAPI middleware keyed off
  `get_current_uid`.
- **No inline evidence-quote highlighting in the original note text** — the `quote_verified`
  flag and the `evidence_quote` field are already in the data returned to the frontend, so this
  is a rendering task (splitting the note text around matched spans), not a data-model change.
- **ICD-10 codes are exactly as approximate as the assessment says is acceptable** — no lookup
  against a real coding table, per the brief's explicit note that this isn't being evaluated.

With one more week, in priority order: re-analysis UI, inline quote highlighting (cheapest
bonus, reuses existing verification data), frontend tests, then caching/rate-limiting.

---

## Deployment

### Backend — Cloud Run

```bash
cd backend
gcloud run deploy note-insight-api \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GEMINI_MODEL=gemini-3.6-flash,CORS_ALLOW_ORIGINS=https://YOUR_FIREBASE_PROJECT_ID.web.app
```

Set `GEMINI_API_KEY` as a secret rather than a plain env var:

```bash
gcloud secrets create gemini-api-key --data-file=- <<< "YOUR_KEY"
gcloud run services update note-insight-api --update-secrets=GEMINI_API_KEY=gemini-api-key:latest
```

Upload the Firebase service account JSON as a secret too (`FIREBASE_SERVICE_ACCOUNT_PATH`
should then point at wherever Cloud Run mounts it), or use Application Default Credentials by
granting the Cloud Run service account the `Firebase Admin` IAM role instead of shipping a key
file at all — the latter is the better long-term answer and is what I'd switch to with more
time.

**`us-central1`, `us-east1`, or `us-west1`** specifically — Cloud Run's always-free quota only
applies in those regions.

### Frontend — Firebase Hosting

```bash
npm install -g firebase-tools
firebase login
# edit .firebaserc: replace YOUR_FIREBASE_PROJECT_ID with your real project id

cd frontend
npm run build
cd ..
firebase deploy --only hosting
```

### Fallback backend host — Render

If avoiding a GCP billing account matters more than avoiding cold starts: connect the repo at
render.com, set the root directory to `backend`, build command `pip install -r
requirements.txt`, start command `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, and add
the same env vars/secrets as above. Free tier sleeps after 15 minutes idle — the first request
after a gap takes 30–60 seconds; this is expected, not a bug.

---

## Prompt

The full prompt sent to Gemini lives in
[`backend/app/prompts/note_analysis_prompt.py`](backend/app/prompts/note_analysis_prompt.py),
versioned via `PROMPT_VERSION` and stored on every analysis document so old and new analyses
of the same note stay individually attributable to the prompt that produced them.

## Sample notes

Three synthetic notes in [`sample_notes/`](sample_notes/) — no real patient data anywhere in
this repo:

- `01_well_documented.txt` — both conditions fully documented, tests the "well_documented" path.
- `02_ambiguous_underdocumented.txt` — diabetes without type/control status, a medication with
  no stated diagnosis, tests the documentation-gap detection this product exists for.
- `03_minimal_edge_case.txt` — no clinical content at all, tests the empty-conditions path.

## Time spent

*(fill in honestly before submitting — the assessment explicitly says this is never held
against a candidate)*
