// Mirrors backend/app/models.py by hand. Keep in sync when the API contract changes.

export type DocumentationStatus =
  | "well_documented"
  | "ambiguous"
  | "mentioned_without_assessment_or_plan";

export type ConditionSource = "ai" | "human_edited" | "human_added";

export type AnalysisStatus = "pending" | "complete" | "failed";

export type ReviewStatus = "pending" | "reviewed";

export interface StoredCondition {
  name: string;
  evidence_quote: string;
  documentation_status: DocumentationStatus;
  status_reason: string;
  icd10_code: string;
  confidence: number;
  quote_verified: boolean;
  source: ConditionSource;
  rejected: boolean;
}

export interface StoredAnalysisOutput {
  conditions: StoredCondition[];
  documentation_gaps: string[];
  summary: string;
}

export interface AnalysisResponse {
  id: string;
  note_id: string;
  created_at: string;
  model_version: string;
  prompt_version: string;
  status: AnalysisStatus;
  ai_output: StoredAnalysisOutput | null;
  review: StoredAnalysisOutput | null;
  review_status: ReviewStatus;
  error_message: string | null;
}

export interface NoteResponse {
  id: string;
  note_text: string;
  pseudonym: string | null;
  visit_date: string | null;
  created_at: string;
  latest_analysis_id: string | null;
}

export interface NoteListItem {
  id: string;
  pseudonym: string | null;
  visit_date: string | null;
  created_at: string;
  condition_count: number;
  review_status: ReviewStatus;
  latest_analysis_id: string | null;
}

export interface NoteWithAnalysis {
  note: NoteResponse;
  analysis: AnalysisResponse;
}

export interface NoteCreateRequest {
  note_text: string;
  pseudonym?: string | null;
  visit_date?: string | null;
}

export interface ReviewPayload {
  conditions: StoredCondition[];
  documentation_gaps: string[];
  summary: string;
}

export interface ConditionMetric {
  name: string;
  times_suggested: number;
  times_edited: number;
  times_rejected: number;
  times_added: number;
}

export interface ReviewMetrics {
  reviewed_analyses: number;
  total_conditions_suggested: number;
  total_edited: number;
  total_rejected: number;
  total_added: number;
  correction_rate: number;
  by_condition: ConditionMetric[];
}
