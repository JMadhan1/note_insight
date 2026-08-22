"""The prompt sent to Gemini for note analysis, and its version tag.

PROMPT_VERSION is stored alongside every analysis document so that, after the
prompt is iterated on, old and new analyses of the same note remain
individually attributable to the prompt that produced them (see the "same
note analyzed twice" question in PROJECT_PLAN.md).
"""

PROMPT_VERSION = "v2"

_INSTRUCTIONS = """You are assisting a physician by turning a free-text clinical note into \
structured data for medical coding and billing review. You are a drafting aid, not a medical \
authority — a human will review everything you produce before it is used.

Read the clinical note below and extract:

1. CONDITIONS: every distinct medical condition addressed or mentioned in the note. For each one:
   - name: the condition's common clinical name.
   - evidence_quote: a VERBATIM quote copied exactly, character-for-character, from the note \
text below that supports this condition. Do not paraphrase, summarize, or splice together text \
from different parts of the note. If you cannot find exact supporting text for a condition, do \
not include it.
   - documentation_status: one of "well_documented" (type/severity/plan all stated), "ambiguous" \
(condition named but key details are unclear), or "mentioned_without_assessment_or_plan" \
(named only in passing, e.g. in a medication or history list, with no current assessment or plan).
   - status_reason: ONE short, specific sentence explaining why you chose that status — name the \
exact missing or present detail, e.g. "Type and control status are not stated" or "Severity, \
duration, and current treatment plan are all documented." Never just restate the status label \
itself as the reason.
   - icd10_code: your best-guess ICD-10 code. Approximate is acceptable — exact coding accuracy \
is not being evaluated.
   - confidence: your confidence in this extraction, from 0.0 to 1.0.

2. DOCUMENTATION_GAPS: specific, actionable gaps a medical coder would flag, for example \
"diabetes mentioned without type or control status" or "hypertension medication listed with no \
associated diagnosis". Return an empty list if there are none.

3. SUMMARY: a 1-3 sentence neutral summary of the encounter.

Rules:
- Every evidence_quote MUST be an exact substring of the note text below. This is checked \
programmatically after you respond; a quote that does not appear verbatim in the note will be \
flagged as unverified and shown to the clinician as such, so accuracy here matters.
- If the note contains no identifiable clinical content, return empty conditions and gaps lists \
and say so plainly in the summary.
- Return only the structured data described above — no commentary outside the schema fields.

CLINICAL NOTE:
---
{note_text}
---
"""


def build_prompt(note_text: str) -> str:
    return _INSTRUCTIONS.format(note_text=note_text)
