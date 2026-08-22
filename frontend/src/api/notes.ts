import { apiRequest } from "./client";
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
