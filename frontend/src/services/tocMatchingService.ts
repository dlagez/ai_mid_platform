import { apiClient } from "./apiClient";

export type TocMatchCreateRequest = {
  plan_document_id: number;
  standard_id: number;
  section_parse_mode?: string | null;
  model?: string | null;
};

export type TocMatchJob = {
  id: number;
  plan_document_id: number;
  plan_parse_result_id: number | null;
  standard_id: number;
  model: string | null;
  status: string;
  match_count: number;
  reviewed_count: number;
  issue_count: number;
  raw_llm_response: unknown;
  error_message: string | null;
  created_by: number | null;
  created_at: string;
  completed_at: string | null;
};

export type TocReviewIssue = {
  standard_basis: string;
  plan_evidence: string;
  problem_description: string;
  rectification_suggestion: string;
};

export type TocMatchItem = {
  id: number;
  job_id: number;
  standard_id: number;
  standard_section_id: number;
  standard_section_no: string | null;
  standard_title: string | null;
  standard_path: string | null;
  plan_document_id: number;
  plan_section_id: number;
  plan_section_no: string | null;
  plan_title: string | null;
  plan_path: string | null;
  match_type: string;
  confidence: number | null;
  reason: string | null;
  review_status: string;
  review_issues: TocReviewIssue[];
  raw_review_response: unknown;
  review_error: string | null;
  reviewed_at: string | null;
  created_at: string;
};

export type TocMatchJobDetail = {
  job: TocMatchJob;
  items: TocMatchItem[];
};

export type TocMatchJobList = {
  items: TocMatchJob[];
  total: number;
  page: number;
  page_size: number;
};

export type TocMatchJobQuery = {
  plan_document_id?: number;
  standard_id?: number;
  status?: string;
  page?: number;
  page_size?: number;
};

export const createTocMatchJob = async (payload: TocMatchCreateRequest) => {
  const { data } = await apiClient.post<TocMatchJobDetail>("/toc-matching/jobs", payload);
  return data;
};

export const listTocMatchJobs = async (query: TocMatchJobQuery = {}) => {
  const { data } = await apiClient.get<TocMatchJobList>("/toc-matching/jobs", { params: query });
  return data;
};

export const getTocMatchJob = async (jobId: number) => {
  const { data } = await apiClient.get<TocMatchJobDetail>(`/toc-matching/jobs/${jobId}`);
  return data;
};

export const reviewTocMatchJob = async (jobId: number, model?: string | null) => {
  const { data } = await apiClient.post<TocMatchJobDetail>(`/toc-matching/jobs/${jobId}/review`, { model: model || null });
  return data;
};

export const reviewTocMatchItem = async (itemId: number, model?: string | null) => {
  const { data } = await apiClient.post<TocMatchItem>(`/toc-matching/items/${itemId}/review`, { model: model || null });
  return data;
};

export const exportTocMatchIssues = async (jobId: number) => {
  const response = await apiClient.get<Blob>(`/toc-matching/jobs/${jobId}/issues/export`, {
    responseType: "blob",
  });

  const contentDisposition = response.headers["content-disposition"];
  let filename = `toc_match_job_${jobId}_issues.xlsx`;
  if (contentDisposition) {
    const match = contentDisposition.match(/filename\*=UTF-8''(.+?)(?:;|$)/);
    if (match) {
      filename = decodeURIComponent(match[1]);
    } else {
      const fallback = contentDisposition.match(/filename="?([^";]+)"?/);
      if (fallback) {
        filename = fallback[1];
      }
    }
  }

  const url = URL.createObjectURL(
    new Blob([response.data], {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
};
