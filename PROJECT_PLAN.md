# Note Insight — Build Plan

Research-backed phased plan for the DoctusTech technical assessment. Built before any code, per the PDF's own instruction ("design and document your data model before you write it").

Time budget: 5 calendar days, ~15–20 hours of work. Phases are ordered by dependency, not by calendar day — but a suggested hour allocation is given per phase so you can self-check pace.

---

## Phase 0 — Decisions & Data Model (no code yet) — ~2 hrs

This is the highest-weighted evaluation area, so it happens first and on paper/markdown, not in code.

### 0.1 Stack decisions (lock these before writing anything)

| Layer | Choice | Why |
|---|---|---|
| Frontend host | **Firebase Hosting** | Same project as Auth/Firestore — one console, one set of credentials, zero extra signup |
| Backend host | **Google Cloud Run** (fallback: **Render**) | Cloud Run: always-free 2M req/month, no cold-sleep penalty, same GCP project as Firebase. Render: zero card required but sleeps after 15 min idle (30–60s cold start) — acceptable but must be disclosed in README so a reviewer opening the link at an odd hour doesn't think it's broken |
| Database | **Firestore (Spark/free plan)** | No card required, 50k reads/20k writes per day (way more than a graded demo needs), pairs natively with Firebase Auth (same UID space, same SDK), and its query model (collection + composite index) maps cleanly onto "all notes for user X, newest first" |
| Auth | **Firebase Authentication**, email/password | Explicitly recommended in the brief; backend verifies the ID token server-side via `firebase_admin.auth.verify_id_token()` — never trusts a client-sent UID |
| LLM SDK | **`google-genai`** Python SDK, `response_schema=<PydanticModel>`, `response_mime_type="application/json"` | Native schema-constrained output — satisfies "validated against a schema, not regex-parsed" without extra plumbing |

**Explicitly avoid**: Fly.io (free tier removed for new accounts in 2024, still gone in 2026), Railway as primary (free allowance is a 30-day $5 trial credit, not durable enough for a 5-day project you might revisit later), SQLite on Cloud Run/Render (both platforms give ephemeral disk — a redeploy or restart silently wipes your database; do not use file-based SQLite on either).

### 0.2 Entity model

Four distinct entities, per the PDF's explicit warning not to collapse them:

```
User (from Firebase Auth — not a Firestore doc you manage, just the UID)
  └── Note              (what the clinician pasted, immutable once created)
        └── Analysis    (one per LLM run — a Note can be analyzed more than once)
              ├── ai_output          (frozen — exactly what Gemini returned, never mutated)
              └── review             (human-edited version, layered on top, nullable until reviewed)
```

**Firestore layout** (subcollections, not one flat document):

```
users/{uid}/notes/{noteId}
  - noteText: string
  - pseudonym: string | null
  - visitDate: timestamp | null
  - createdAt: timestamp
  - latestAnalysisId: string | null   (denormalized pointer for the history list)

users/{uid}/notes/{noteId}/analyses/{analysisId}
  - createdAt: timestamp
  - modelVersion: string              (e.g. "gemini-2.5-flash", for future "second AI provider" support)
  - promptVersion: string             (so you can tell which prompt iteration produced this)
  - status: "pending" | "complete" | "failed"
  - aiOutput: {                       ← FROZEN, written once, never edited after creation
      conditions: [{ name, evidenceQuote, quoteVerified: bool, documentationStatus, icd10Code, confidence }],
      documentationGaps: [string],
      summary: string
    }
  - review: {                         ← null until a human touches it
      reviewedAt: timestamp,
      conditions: [{ ...same shape, plus: source: "ai" | "human_edited" | "human_added", rejected: bool }],
      documentationGaps: [string],
      summary: string
    } | null
  - reviewStatus: "pending" | "reviewed"   (denormalized, drives the history list badge)
```

**Why subcollections over one flat "analysis" document per note**: it directly answers the brief's own test question — "what happens when the same note is analyzed twice, after you improve your prompt?" Each re-analysis is a new sibling document under the same note; nothing is overwritten, nothing disappears, and `latestAnalysisId` on the parent note tells the UI which one to show by default while old ones stay queryable. A flat model forces an awkward choice between overwriting history or bolting an array onto one document that grows unboundedly.

**Why `aiOutput` and `review` are separate objects, not one mutable object with a `wasEdited` flag per field**: the brief calls this "the single most valuable dataset the product will ever produce" — the diff between what the model said and what the human corrected. That diff has to be reconstructable forever, which means the original can never be overwritten in place, only shadowed by a second object.

### 0.3 The query that matters

"All notes for user X, newest first" → `users/{uid}/notes` ordered by `createdAt desc`. Because it's a subcollection scoped to `{uid}`, Firestore's security rules can enforce user isolation *at the database layer* (`allow read: if request.auth.uid == uid`), not just in application code — this directly answers the brief's hard requirement that a user can never see another user's data, and it holds even if a backend route had a bug. Needs one composite index (`createdAt desc`), which Firestore will prompt you to create the first time you run the query.

### 0.4 Write this into README.md now (skeleton, fill in as you go)

- [ ] Local setup instructions (placeholder, fill in Phase 1–2)
- [ ] Data model section — paste Phase 0.2/0.3 reasoning here, refine as reality diverges from plan
- [ ] Design decisions section — start a running list *now*, don't reconstruct it from memory on day 5
- [ ] "What I'd build next / what I left unfinished" — start a scratch list now, append as you cut scope

---

## Phase 1 — Backend skeleton + deploy pipeline, end to end — ~3 hrs

Deploy a trivial "hello world" FastAPI service to Cloud Run **before** building real features. Getting the deploy pipeline working on day 1 with nothing in it means day 5 isn't a deployment fire drill — this is the single highest-leverage move in the whole plan given the "must be live, no local running" requirement.

1. `fastapi` + `uvicorn` skeleton, one `GET /health` route.
2. Dockerfile (Cloud Run needs a container) or use Cloud Run's buildpack auto-detection for Python.
3. Deploy it. Confirm the public URL responds. This proves the whole pipeline (build → deploy → public URL) works while the stakes are zero.
4. Set up Firebase project (Auth + Firestore) in the console. Add web app config for the frontend later.
5. Add the `firebase_admin` verification dependency (`get_current_user`) and a protected `GET /me` route that echoes the verified UID. Deploy again, confirm a real ID token round-trips correctly. This is the auth requirement's core mechanism — prove it works before any UI exists.
6. Pydantic settings for env vars (`GEMINI_API_KEY`, Firebase service account path). Confirm the Gemini key never appears in any response payload or log line — check this explicitly, it's an automatic-fail item.

**Checkpoint**: public URL, `/health` returns 200, `/me` rejects unauthenticated requests and returns a UID for a valid token. Nothing else exists yet. That's correct for this phase.

---

## Phase 2 — Core AI pipeline (backend only, test via API docs / curl) — ~4 hrs

Build and prove the hardest, highest-weighted part before touching the frontend.

1. Define the Pydantic schema for the AI's output (`ConditionModel`, `AnalysisOutputModel` — name, evidenceQuote, documentationStatus as a `Literal`/enum, icd10Code, confidence as bounded float; documentationGaps: `list[str]`; summary: `str`).
2. Write the Gemini prompt as its own file (`backend/prompts/note_analysis.md` or `.py` constant) — this is a required deliverable, treat it as a first-class artifact, not an inline string buried in a function.
3. Call Gemini with `response_schema=AnalysisOutputModel`, `response_mime_type="application/json"`. Use `response.parsed` to get a typed object directly.
4. **Evidence verification**: after parsing, for each condition run a normalized substring check — lowercase both sides, collapse whitespace, strip trailing punctuation, then confirm the quote is a literal substring of the note. Set `quoteVerified: false` (don't silently drop it) on any condition whose quote doesn't match — surfaced in the UI later as "unverified — check this one." This is your defensible answer to "how do you know the model didn't make this up?"
5. **Malformed-output handling, decided deliberately** (write the decision in the README, don't leave it implicit):
   - Pydantic validation failure on the raw Gemini response → catch it, store `status: "failed"` with the raw text preserved for debugging, return a typed error to the frontend (not a 500 crash).
   - Recommend: **one retry** with a short "your last response didn't match the schema, try again" follow-up before giving up — cheap and meaningfully improves reliability. Don't retry indefinitely.
6. `POST /notes` (create note + trigger analysis) and `GET /notes/{id}/analyses/{id}` routes, both behind the auth dependency, both scoped to the requesting UID (never trust an ID path param alone — verify the parent note belongs to the caller).
7. Edge cases to test manually right now with curl/API docs, before UI exists: empty note body, a note that's a single word, a ~3000-word note, and a request with no/garbage auth token.

**Checkpoint**: you can `curl` a note in and get back a schema-valid, quote-verified analysis, or a clean typed failure — no crashes, no hangs, no secrets in the response.

---

## Phase 3 — Frontend core: auth + submission + results — ~4 hrs

Bare styling is fine here; structure and typing are what's graded.

1. Firebase Auth UI: signup/login forms (email+password), store the ID token, attach it as `Authorization: Bearer <token>` on every API call.
2. Route guard: unauthenticated users see the login screen, full stop — no flash of protected content.
3. Note submission form: textarea + optional pseudonym/visit-date fields. Client-side word-count guard as a UX nicety, not a substitute for backend validation.
4. Loading/success/error states as real UI states (a small state machine: `idle | submitting | success | error`), not a boolean spinner flag — the brief explicitly calls out "must not look frozen or lie about what happened."
5. Results view: conditions list (name, quoted evidence, doc status, ICD-10 code, confidence), a visual flag on any `quoteVerified: false` item, documentation gaps list, summary.
6. TypeScript types for the API contract mirrored from the backend Pydantic models by hand (or generate from an OpenAPI schema if time allows) — no `any`.

**Checkpoint**: a logged-in user can paste a note, see a loading state, and see a real structured result rendered from your own deployed backend — full loop, ugly but working.

---

## Phase 4 — Human review & correction preservation — ~3 hrs

The part the brief says it cares about most, on the frontend side.

1. Inline edit on each condition field; a reject toggle per condition (soft — sets `rejected: true`, doesn't delete); an "add condition" affordance for ones the model missed.
2. "Save review" writes the `review` object to the analysis document — `aiOutput` is never touched.
3. Explicit UI distinction between "AI said" and "you corrected" — even a simple diff badge ("edited", "added by you", "rejected") satisfies the brief's ask to answer "what did the model say vs. what did the human change."
4. `reviewStatus` flips `pending → reviewed` on save.

**Checkpoint**: edit a result, reload the page, confirm both the original AI output and your edits are independently visible and neither overwrote the other.

---

## Phase 5 — History view — ~1.5 hrs

1. `GET /notes` (paginated or just capped at ~50, fine for a demo) → list ordered by `createdAt desc`, each row showing date, pseudonym, condition count, review status.
2. Click-through to the full analysis (reuse the Phase 3/4 components).

**Checkpoint**: create 2–3 notes, confirm they list newest-first, confirm clicking one opens the right analysis with review state intact.

---

## Phase 6 — Robustness & security pass — ~2 hrs

Do this as its own deliberate pass, not as an afterthought — it's a full scored category.

1. **Cross-user access attempt**: log in as user A, note an analysis ID, log in as user B, try to hit that ID directly via the API. Confirm a 403/404, not data. Do this for real, don't just reason about it.
2. Empty note, whitespace-only note, a note far over 3000 words, non-English text, a note containing no clinical content at all — confirm each gets a sane response, not a crash.
3. Kill your Gemini key temporarily (or point at a bad model name) and confirm the failure path degrades to your typed error state, not a stack trace on the page.
4. Re-run the "no secrets in repo" check: grep the frontend bundle and the git history for the Gemini key.
5. Basic rate/size guard on the note-submission endpoint (reject oversized payloads at the Pydantic/FastAPI boundary) even if you skip full rate limiting as a bonus item.

---

## Phase 7 — UI/UX polish — ~1.5–2 hrs

Deliberately last, per the brief's own framing ("visual polish is worth points but is not the main event"). Everything above should work before this starts.

1. Visual hierarchy pass: make the doc-status flag (well documented / ambiguous / no plan) and the unverified-quote flag scannable at a glance — this is the actual product value, so it's worth the polish budget.
2. Consistent spacing/typography, a real empty state for "no notes yet," a real 404/loading skeleton instead of layout jump.
3. Nothing exotic — a clean information hierarchy beats animation, per the brief.

---

## Phase 8 — Optional/bonus features (only if Phases 0–7 are solid) — remaining time

Pick at most 1–2, don't spread thin. Suggested priority given the "5 senior-signal" framing of the brief:

1. **Meaningful automated tests around schema validation and failure paths** (highest ROI — directly reinforces the "robustness" scoring category with evidence, not just claims).
2. **Inline evidence-quote highlighting** in the original note text (cheap, visually strong, reuses the substring-match logic you already built in Phase 2.4).
3. Caching identical notes (skip if short on time — lowest signal-per-hour of the listed bonuses for a grader).
4. Skip streaming, PDF/image upload, and the metrics view unless everything else is done with time to spare — each is a real chunk of work for one bullet point of credit.

---

## Phase 9 — Deliverables packaging — ~1.5 hrs

1. Finish README: local run instructions (test them on a clean checkout if possible), data model writeup (Phase 0 content, updated for reality), 3–4 design decisions with alternatives considered (deployment platform choice, Firestore vs. Postgres, subcollection vs. flat schema, retry-once vs. fail-fast on malformed output are all good candidates — you already have the reasoning from Phase 0–2), "what I'd build next," honest hours spent.
2. Confirm the prompt file is committed and easy to find.
3. Write 2–3 synthetic sample notes (varied: one clean, one deliberately ambiguous/under-documented, one edge case like a very short note) into the repo.
4. Review commit history — if it's one giant commit at this point, that's a real deduction; if you've been committing incrementally through the phases above this is already handled.
5. Create/confirm a test account, or verify signup works cleanly for a stranger.

---

## Suggested day mapping (5 days, ~15–20 hrs)

| Day | Phases |
|---|---|
| 1 | 0 (decisions + data model on paper) + 1 (skeleton deployed, auth proven) |
| 2 | 2 (AI pipeline, schema validation, quote verification) |
| 3 | 3 (frontend core) + 4 (review) |
| 4 | 5 (history) + 6 (robustness/security pass) |
| 5 | 7 (polish) + 8 (bonus, if time) + 9 (README/deliverables) + submit with buffer, don't submit at the deadline instant |

---

## Open questions worth emailing DoctusTech about (per their own "ambiguity is sometimes deliberate, asking is how you find out" note)

- Is a specific ICD-10 coding standard/version expected, or is "plausible-looking code" genuinely sufficient (the brief says yes, but confirming costs nothing)?
- Any preference between Cloud Run and Render given the cold-start tradeoff, or is that entirely the candidate's call to make and justify?

---

*This plan is the artifact requested — no code has been written yet. Implementation starts only on explicit go-ahead.*
