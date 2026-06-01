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
  evidence_code: string | null;
  evidence_text: string;
  object_terms: string[];
  task_id: number | null;
  document_id: number;
  section_id: number;
  chapter_title: string | null;
  chapter_path: string | null;
  source_text: string | null;
  confidence: number | null;
  status: string;
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
  section: {
    id: number;
    level: number;
    title: string;
    section_no: string | null;
  } | null;
};

export type CheckpointMatchListResult = {
  items: CheckpointMatchWithCheckpoint[];
  total: number;
  page?: number | null;
  page_size?: number | null;
};

export type CheckpointMatchListQuery = {
  status?: string;
  matched_only?: boolean;
  page?: number;
  page_size?: number;
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
  skipped_count: number;
  failed: Array<Record<string, unknown>>;
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

export const buildChapterProfiles = async (taskId: number) => {
  const { data } = await apiClient.post<BuildChapterProfilesResult>(`/review-tasks/${taskId}/build-chapter-profiles`);
  return data;
};

export const matchReviewCheckpoints = async (taskId: number) => {
  const { data } = await apiClient.post<MatchCheckpointsResult>(`/review-tasks/${taskId}/match-checkpoints`);
  return data;
};

export const listReviewTaskCheckpointMatches = async (taskId: number, query: CheckpointMatchListQuery = {}) => {
  const { data } = await apiClient.get<CheckpointMatchListResult>(`/review-tasks/${taskId}/checkpoint-matches`, {
    params: query,
  });
  return data;
};

export const runCheckpointReview = async (taskId: number) => {
  const { data } = await apiClient.post<RunCheckpointReviewResult>(`/review-tasks/${taskId}/run-checkpoint-review`);
  return data;
};
