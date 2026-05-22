import { apiClient } from "./apiClient";

export type StandardDocument = {
  id: number;
  standard_code: string | null;
  standard_name: string;
  standard_type: string | null;
  version: string | null;
  effective_date: string | null;
  source_file_id: number | null;
  source_document_id: number | null;
  status: string;
  description: string | null;
  created_by: number | null;
  created_at: string;
  updated_at: string;
};

export type StandardDocumentPayload = {
  standard_code?: string | null;
  standard_name?: string;
  standard_type?: string | null;
  version?: string | null;
  effective_date?: string | null;
  source_file_id?: number | null;
  source_document_id?: number | null;
  status?: string;
  description?: string | null;
};

export type StandardDocumentListResult = {
  items: StandardDocument[];
  total: number;
};

export type ImportStandardRequest = {
  document_id: number;
  standard_code?: string | null;
  standard_name: string;
  standard_type?: string | null;
  version?: string | null;
  effective_date?: string | null;
  description?: string | null;
};

export type ImportStandardResult = {
  standard_id: number;
  clause_count: number;
};

export type StandardClause = {
  id: number;
  standard_id: number;
  parent_id: number | null;
  chapter_no: string | null;
  clause_no: string | null;
  title: string | null;
  content: string;
  level: number;
  path: string | null;
  is_mandatory: boolean;
  keywords: string[];
  applicable_work_types: string[];
  source_section_id: number | null;
  order_no: number;
  embedding_id: string | null;
  created_at: string;
  updated_at: string;
};

export type StandardClausePayload = {
  parent_id?: number | null;
  chapter_no?: string | null;
  clause_no?: string | null;
  title?: string | null;
  content?: string;
  level?: number;
  path?: string | null;
  is_mandatory?: boolean;
  keywords?: string[];
  applicable_work_types?: string[];
  order_no?: number;
  embedding_id?: string | null;
};

export type StandardClauseQuery = {
  keyword?: string;
  clause_no?: string;
  is_mandatory?: boolean;
  work_type?: string;
  page?: number;
  page_size?: number;
};

export type StandardClauseListResult = {
  items: StandardClause[];
  total: number;
  page: number;
  page_size: number;
};

export type GenerateRuleCandidatesRequest = {
  clause_ids: number[];
  use_llm: boolean;
};

export type GenerateRuleCandidatesResult = {
  created_count: number;
  candidate_ids: number[];
  failed: Array<Record<string, unknown>>;
  skipped: Array<Record<string, unknown>>;
};

export const listStandards = async () => {
  const { data } = await apiClient.get<StandardDocumentListResult>("/standards");
  return data;
};

export const getStandard = async (id: number) => {
  const { data } = await apiClient.get<StandardDocument>(`/standards/${id}`);
  return data;
};

export const createStandard = async (payload: StandardDocumentPayload) => {
  const { data } = await apiClient.post<StandardDocument>("/standards", payload);
  return data;
};

export const updateStandard = async (id: number, payload: StandardDocumentPayload) => {
  const { data } = await apiClient.patch<StandardDocument>(`/standards/${id}`, payload);
  return data;
};

export const archiveStandard = async (id: number) => {
  const { data } = await apiClient.delete<StandardDocument>(`/standards/${id}`);
  return data;
};

export const importStandardFromDocument = async (payload: ImportStandardRequest) => {
  const { data } = await apiClient.post<ImportStandardResult>("/standards/import-from-document", payload);
  return data;
};

export const listStandardClauses = async (standardId: number, query: StandardClauseQuery = {}) => {
  const { data } = await apiClient.get<StandardClauseListResult>(`/standards/${standardId}/clauses`, {
    params: query,
  });
  return data;
};

export const createStandardClause = async (standardId: number, payload: StandardClausePayload) => {
  const { data } = await apiClient.post<StandardClause>(`/standards/${standardId}/clauses`, payload);
  return data;
};

export const getStandardClause = async (clauseId: number) => {
  const { data } = await apiClient.get<StandardClause>(`/standard-clauses/${clauseId}`);
  return data;
};

export const updateStandardClause = async (clauseId: number, payload: StandardClausePayload) => {
  const { data } = await apiClient.patch<StandardClause>(`/standard-clauses/${clauseId}`, payload);
  return data;
};

export const deleteStandardClause = async (clauseId: number) => {
  const { data } = await apiClient.delete<StandardClause>(`/standard-clauses/${clauseId}`);
  return data;
};

export const generateRuleCandidates = async (standardId: number, payload: GenerateRuleCandidatesRequest) => {
  const { data } = await apiClient.post<GenerateRuleCandidatesResult>(
    `/standards/${standardId}/generate-rule-candidates`,
    payload,
  );
  return data;
};
