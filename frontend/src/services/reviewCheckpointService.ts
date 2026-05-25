import { apiClient } from "./apiClient";

export type ReviewCheckpoint = {
  id: number;
  checkpoint_code: string | null;
  checkpoint_name: string;
  checkpoint_type: string;
  domain: string | null;
  subdomain: string | null;
  work_type: string | null;
  standard_id: number | null;
  clause_id: number | null;
  clause_no: string | null;
  clause_text: string | null;
  chapter_types: string[];
  target_objects: string[];
  target_parameters: string[];
  keywords: string[];
  check_goal: string | null;
  check_method: string | null;
  expected_items: string[];
  forbidden_items: string[];
  parameters: Record<string, unknown>;
  applicable_condition: Record<string, unknown>;
  risk_level: string;
  is_mandatory: boolean;
  priority: number;
  status: string;
  created_at: string;
  updated_at: string;
};

export type ReviewCheckpointPayload = {
  checkpoint_code?: string | null;
  checkpoint_name?: string;
  checkpoint_type?: string;
  domain?: string | null;
  subdomain?: string | null;
  work_type?: string | null;
  standard_id?: number | null;
  clause_id?: number | null;
  clause_no?: string | null;
  clause_text?: string | null;
  chapter_types?: string[];
  target_objects?: string[];
  target_parameters?: string[];
  keywords?: string[];
  check_goal?: string | null;
  check_method?: string | null;
  expected_items?: string[];
  forbidden_items?: string[];
  parameters?: Record<string, unknown>;
  applicable_condition?: Record<string, unknown>;
  risk_level?: string;
  is_mandatory?: boolean;
  priority?: number;
  status?: string;
};

export type ReviewCheckpointQuery = {
  status?: string;
  checkpoint_type?: string;
  domain?: string;
  work_type?: string;
  keyword?: string;
  page?: number;
  page_size?: number;
};

export type ReviewCheckpointListResult = {
  items: ReviewCheckpoint[];
  total: number;
  page: number;
  page_size: number;
};

export type GenerateCheckpointsRequest = {
  clause_ids: number[];
  use_llm: boolean;
};

export type GenerateCheckpointsResult = {
  created_count: number;
  checkpoint_ids: number[];
  failed: Array<Record<string, unknown>>;
  skipped: Array<Record<string, unknown>>;
};

export const listReviewCheckpoints = async (query: ReviewCheckpointQuery = {}) => {
  const { data } = await apiClient.get<ReviewCheckpointListResult>("/review-checkpoints", { params: query });
  return data;
};

export const createReviewCheckpoint = async (payload: ReviewCheckpointPayload) => {
  const { data } = await apiClient.post<ReviewCheckpoint>("/review-checkpoints", payload);
  return data;
};

export const updateReviewCheckpoint = async (id: number, payload: ReviewCheckpointPayload) => {
  const { data } = await apiClient.patch<ReviewCheckpoint>(`/review-checkpoints/${id}`, payload);
  return data;
};

export const deleteReviewCheckpoint = async (id: number) => {
  const { data } = await apiClient.delete<ReviewCheckpoint>(`/review-checkpoints/${id}`);
  return data;
};

export const generateReviewCheckpoints = async (payload: GenerateCheckpointsRequest) => {
  const { data } = await apiClient.post<GenerateCheckpointsResult>(
    "/review-checkpoints/generate-from-standard-clauses",
    payload,
  );
  return data;
};
