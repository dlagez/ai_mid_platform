import { apiClient } from "./apiClient";

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

export type ReviewTaskStartResult = {
  id: number;
  status: string;
  version: number | null;
  total_issue_count: number | null;
  critical_issue_count: number | null;
  major_issue_count: number | null;
  minor_issue_count: number | null;
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
  ai_reason: string | null;
  suggestion: string | null;
  status: string;
  expert_comment: string | null;
  confirmed_by: number | null;
  confirmed_at: string | null;
  created_at: string;
  updated_at: string;
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

export const startReviewTask = async (id: number) => {
  const { data } = await apiClient.post<ReviewTaskStartResult>(`/review-tasks/${id}/start`);
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
