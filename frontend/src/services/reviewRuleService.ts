import { apiClient } from "./apiClient";

export type ReviewRuleCandidate = {
  id: number;
  standard_id: number | null;
  clause_id: number | null;
  rule_name: string | null;
  rule_type: string | null;
  work_type: string | null;
  check_object: string | null;
  operator: string | null;
  threshold_value: string | null;
  unit: string | null;
  required_items: string[];
  forbidden_items: string[];
  applicable_condition: Record<string, unknown>;
  risk_level_suggestion: string | null;
  source_clause_text: string | null;
  ai_confidence: number | null;
  ai_reason: string | null;
  status: string;
  reviewed_by: number | null;
  reviewed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type ReviewRuleCandidatePayload = {
  rule_name?: string | null;
  rule_type?: string | null;
  work_type?: string | null;
  check_object?: string | null;
  operator?: string | null;
  threshold_value?: string | null;
  unit?: string | null;
  required_items?: string[];
  forbidden_items?: string[];
  applicable_condition?: Record<string, unknown>;
  risk_level_suggestion?: string | null;
  ai_confidence?: number | null;
  ai_reason?: string | null;
  status?: string;
};

export type ReviewRuleCandidateQuery = {
  status?: string;
  standard_id?: number;
  rule_type?: string;
  work_type?: string;
  keyword?: string;
  page?: number;
  page_size?: number;
};

export type ReviewRuleCandidateListResult = {
  items: ReviewRuleCandidate[];
  total: number;
  page: number;
  page_size: number;
};

export type ReviewRule = {
  id: number;
  source_candidate_id: number | null;
  source_type: string | null;
  standard_id: number | null;
  clause_id: number | null;
  rule_name: string;
  rule_type: string;
  work_type: string | null;
  check_object: string | null;
  operator: string | null;
  threshold_value: string | null;
  unit: string | null;
  required_items: string[];
  forbidden_items: string[];
  applicable_condition: Record<string, unknown>;
  risk_level: string;
  status: string;
  created_by: number | null;
  created_at: string;
  updated_at: string;
};

export const listRuleCandidates = async (query: ReviewRuleCandidateQuery = {}) => {
  const { data } = await apiClient.get<ReviewRuleCandidateListResult>("/rule-candidates", { params: query });
  return data;
};

export const getRuleCandidate = async (id: number) => {
  const { data } = await apiClient.get<ReviewRuleCandidate>(`/rule-candidates/${id}`);
  return data;
};

export const updateRuleCandidate = async (id: number, payload: ReviewRuleCandidatePayload) => {
  const { data } = await apiClient.patch<ReviewRuleCandidate>(`/rule-candidates/${id}`, payload);
  return data;
};

export const approveRuleCandidate = async (id: number) => {
  const { data } = await apiClient.post<ReviewRule>(`/rule-candidates/${id}/approve`);
  return data;
};

export const rejectRuleCandidate = async (id: number) => {
  const { data } = await apiClient.post<ReviewRuleCandidate>(`/rule-candidates/${id}/reject`);
  return data;
};
