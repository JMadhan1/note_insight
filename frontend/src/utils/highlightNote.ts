import type { StoredCondition } from "../types/api";

export interface NoteSegment {
  text: string;
  status: StoredCondition["documentation_status"] | null;
  conditionIndex: number | null;
}

/**
 * Splits the original note text into plain and highlighted segments, one per condition's
 * evidence quote. Case-insensitive exact match — Gemini is instructed to copy quotes
 * verbatim, so this finds the real span in almost every case; a quote that can't be found
 * (already flagged quote_verified: false elsewhere) is simply left unhighlighted rather
 * than guessed at.
 */
export function buildHighlightedSegments(noteText: string, conditions: StoredCondition[]): NoteSegment[] {
  interface Match {
    start: number;
    end: number;
    status: StoredCondition["documentation_status"];
    conditionIndex: number;
  }

  const lowerNote = noteText.toLowerCase();
  const matches: Match[] = [];

  conditions.forEach((condition, index) => {
    if (condition.rejected) return;
    const quote = condition.evidence_quote.trim();
    if (!quote) return;
    const start = lowerNote.indexOf(quote.toLowerCase());
    if (start === -1) return;
    matches.push({ start, end: start + quote.length, status: condition.documentation_status, conditionIndex: index });
  });

  matches.sort((a, b) => a.start - b.start);

  const merged: Match[] = [];
  for (const match of matches) {
    const last = merged[merged.length - 1];
    if (last && match.start < last.end) continue;
    merged.push(match);
  }

  const segments: NoteSegment[] = [];
  let cursor = 0;
  for (const match of merged) {
    if (match.start > cursor) {
      segments.push({ text: noteText.slice(cursor, match.start), status: null, conditionIndex: null });
    }
    segments.push({
      text: noteText.slice(match.start, match.end),
      status: match.status,
      conditionIndex: match.conditionIndex,
    });
    cursor = match.end;
  }
  if (cursor < noteText.length) {
    segments.push({ text: noteText.slice(cursor), status: null, conditionIndex: null });
  }

  return segments;
}
