import { API_BASE_URL, ApiError, apiRequest, authHeader, uploadFile } from "./client";
import type {
  AnalysisResponse,
  NoteCreateRequest,
  NoteListItem,
  NoteResponse,
  NoteWithAnalysis,
  ReviewMetrics,
  ReviewPayload,
} from "../types/api";

export function submitNote(payload: NoteCreateRequest): Promise<NoteWithAnalysis> {
  return apiRequest<NoteWithAnalysis>("/notes", { method: "POST", body: payload });
}

export function listNotes(): Promise<NoteListItem[]> {
  return apiRequest<NoteListItem[]>("/notes");
}

export function getNote(noteId: string): Promise<NoteResponse> {
  return apiRequest<NoteResponse>(`/notes/${noteId}`);
}

export function getAnalysis(noteId: string, analysisId: string): Promise<AnalysisResponse> {
  return apiRequest<AnalysisResponse>(`/notes/${noteId}/analyses/${analysisId}`);
}

export function getMetrics(): Promise<ReviewMetrics> {
  return apiRequest<ReviewMetrics>("/notes/metrics");
}

export interface StreamResult {
  noteId: string;
  analysisId: string;
  errorMessage: string | null;
}

/**
 * Streams the analysis via Server-Sent Events, calling onDelta as each raw JSON text
 * chunk arrives (for a live "watch it think" preview), and resolving once the backend
 * sends a `complete` or `error` event. The saved result is identical either way to the
 * non-streaming submitNote() — streaming only changes what's shown while waiting.
 */
export async function submitNoteStreaming(
  payload: NoteCreateRequest,
  onDelta: (text: string) => void,
): Promise<StreamResult> {
  const headers = await authHeader();

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/notes/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...headers },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new ApiError(0, "Could not reach the server. Check your connection and try again.");
  }

  if (!response.ok || !response.body) {
    throw new ApiError(response.status, "Could not start the analysis stream.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result: StreamResult | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let separatorIndex = buffer.indexOf("\n\n");
    while (separatorIndex !== -1) {
      const rawEvent = buffer.slice(0, separatorIndex);
      buffer = buffer.slice(separatorIndex + 2);

      const eventMatch = /^event: (.+)$/m.exec(rawEvent);
      const dataMatch = /^data: (.+)$/m.exec(rawEvent);
      if (eventMatch && dataMatch) {
        const eventType = eventMatch[1];
        const data = JSON.parse(dataMatch[1]) as Record<string, string>;

        if (eventType === "delta" && typeof data.text === "string") {
          onDelta(data.text);
        } else if (eventType === "complete") {
          result = { noteId: data.note_id, analysisId: data.analysis_id, errorMessage: null };
        } else if (eventType === "error") {
          result = { noteId: data.note_id, analysisId: data.analysis_id, errorMessage: data.message };
        }
      }
      separatorIndex = buffer.indexOf("\n\n");
    }
  }

  if (!result) {
    throw new ApiError(0, "The analysis stream ended unexpectedly.");
  }
  return result;
}

export interface ExtractedText {
  extracted_text: string;
}

/** Transcribes an uploaded photo or PDF of a note into plain text via Gemini — the
 * result is meant to fill the note textarea for review, exactly like typed or
 * dictated text, not to be trusted or saved directly. */
export function extractTextFromFile(file: File): Promise<ExtractedText> {
  return uploadFile<ExtractedText>("/notes/extract-text", file);
}

export function submitReview(
  noteId: string,
  analysisId: string,
  payload: ReviewPayload,
): Promise<AnalysisResponse> {
  return apiRequest<AnalysisResponse>(`/notes/${noteId}/analyses/${analysisId}/review`, {
    method: "POST",
    body: payload,
  });
}
