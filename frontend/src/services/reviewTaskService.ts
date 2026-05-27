import { apiClient } from "./apiClient";
import type { ReviewCheckpoint } from "./reviewCheckpointService";

export type ReviewTask = {
  id: number;
  task_name: string | null;
  plan_document_id: number;
  template_id: number | null;
  work_type: string | null;
  review_mode: string;
  status: string;
  version: number;
  progress: number;
  total_issue_count: number;
  critical_issue_count: number;
  major_issue_count: number;
  minor_issue_count: number;
  created_by: number | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  error_message: string | null;
};

export type ReviewTaskCreate = {
  task_name?: string | null;
  plan_document_id: number;
  template_id?: number | null;
  work_type?: string | null;
  review_mode?: string;
};

export type ReviewTaskListQuery = {
  status?: string;
  plan_document_id?: number;
  page?: number;
  page_size?: number;
};

export type ReviewTaskListResult = {
  items: ReviewTask[];
  total: number;
  page: number;
  page_size: number;
};

export type ReviewIssue = {
  id: number;
  task_id: number;
  version: number;
  issue_type: string | null;
  risk_level: string | null;
  issue_title: string | null;
  issue_description: string | null;
  plan_section_id: number | null;
  plan_section_title: string | null;
  plan_original_text: string | null;
  source_type: string | null;
  source_rule_id: number | null;
  source_template_rule_id: number | null;
  standard_clause_id: number | null;
  checkpoint_id: number | null;
  match_result_id: number | null;
  confidence: number | null;
  confidence_reason: string | null;
  ai_reason: string | null;
  suggestion: string | null;
  status: string;
  expert_comment: string | null;
  confirmed_by: number | null;
  confirmed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type ChapterProfileParameter =
  | string
  | {
      name?: string;
      value?: string | number;
      unit?: string;
      source_text?: string;
      [key: string]: unknown;
    };

export type ChapterReviewProfile = {
  id: number;
  task_id: number | null;
  document_id: number;
  section_id: number;
  chapter_title: string | null;
  chapter_path: string | null;
  chapter_type: string | null;
  main_domain: string | null;
  subdomains: string[];
  construction_objects: Array<Record<string, unknown>>;
  materials: string[];
  mentioned_parameters: ChapterProfileParameter[];
  mentioned_methods: string[];
  mentioned_risks: string[];
  mentioned_standards: string[];
  expected_missing_objects: string[];
  summary: string | null;
  confidence: number | null;
  created_at: string;
  updated_at: string;
};

export type BuildChapterProfilesResult = {
  task_id: number | null;
  document_id: number;
  created_count: number;
  updated_count: number;
  failed: Array<Record<string, unknown>>;
  items: ChapterReviewProfile[];
};

export type CheckpointMatchResult = {
  id: number;
  task_id: number;
  section_id: number;
  checkpoint_id: number;
  match_score: number;
  match_reason: string | null;
  match_dimensions: Record<string, unknown>;
  status: string;
  created_at: string;
  updated_at: string;
};

export type CheckpointMatchWithCheckpoint = CheckpointMatchResult & {
  checkpoint: ReviewCheckpoint | null;
};

export type CheckpointMatchListResult = {
  items: CheckpointMatchWithCheckpoint[];
  total: number;
};

export type MatchCheckpointsResult = {
  task_id: number;
  selected_count: number;
  candidate_count: number;
  items: CheckpointMatchResult[];
};

export type RunCheckpointReviewResult = {
  task_id: number;
  executed_count: number;
  issue_count: number;
  skipped_count: number;
  failed: Array<Record<string, unknown>>;
};

export type ReviewIssueListQuery = {
  version?: number;
  status?: string;
  risk_level?: string;
  issue_type?: string;
  page?: number;
  page_size?: number;
};

export type ReviewIssueListResult = {
  items: ReviewIssue[];
  total: number;
  page: number;
  page_size: number;
};

export type ReviewIssueConfirmRequest = {
  action: "accepted" | "ignored" | "modified" | "closed";
  expert_comment?: string | null;
  issue_title?: string | null;
  issue_description?: string | null;
  risk_level?: string | null;
  suggestion?: string | null;
};

export const listReviewTasks = async (query: ReviewTaskListQuery = {}) => {
  const { data } = await apiClient.get<ReviewTaskListResult>("/review-tasks", { params: query });
  return data;
};

export const createReviewTask = async (payload: ReviewTaskCreate) => {
  const { data } = await apiClient.post<ReviewTask>("/review-tasks", payload);
  return data;
};

export const getReviewTask = async (id: number) => {
  const { data } = await apiClient.get<ReviewTask>(`/review-tasks/${id}`);
  return data;
};

export const listReviewTaskIssues = async (taskId: number, query: ReviewIssueListQuery = {}) => {
  const { data } = await apiClient.get<ReviewIssueListResult>(`/review-tasks/${taskId}/issues`, {
    params: query,
  });
  return data;
};

export const confirmReviewIssue = async (issueId: number, payload: ReviewIssueConfirmRequest) => {
  const { data } = await apiClient.post<ReviewIssue>(`/review-issues/${issueId}/confirm`, payload);
  return data;
};

export const buildChapterProfiles = async (taskId: number) => {
  const { data } = await apiClient.post<BuildChapterProfilesResult>(`/review-tasks/${taskId}/build-chapter-profiles`);
  return data;
};

export const matchReviewCheckpoints = async (taskId: number) => {
  const { data } = await apiClient.post<MatchCheckpointsResult>(`/review-tasks/${taskId}/match-checkpoints`);
  return data;
};

export const listReviewTaskCheckpointMatches = async (taskId: number) => {
  const { data } = await apiClient.get<CheckpointMatchListResult>(`/review-tasks/${taskId}/checkpoint-matches`);
  return data;
};

export const runCheckpointReview = async (taskId: number) => {
  const { data } = await apiClient.post<RunCheckpointReviewResult>(`/review-tasks/${taskId}/run-checkpoint-review`);
  return data;
};
