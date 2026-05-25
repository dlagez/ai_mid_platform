import { apiClient } from "./apiClient";

export type SectionParseMode = "docling_auto" | "docling_toc_outline" | "word_native";

export type SectionParseModeItem = {
  mode: SectionParseMode;
  label: string;
  description: string;
};

export type DocumentRecord = {
  id: number;
  file_name: string;
  file_path: string;
  file_size: number;
  document_type: DocumentType;
  section_parse_mode: SectionParseMode;
  parse_status: string;
  created_at: string;
};

export type DocumentType = "template" | "construction_plan";

export type DocumentUploadResult = {
  id: number;
  file_name: string;
  document_type: DocumentType;
  section_parse_mode: SectionParseMode;
  status: string;
};

export type DocumentParseResult = {
  id: number;
  file_name: string;
  section_parse_mode: SectionParseMode;
  parse_status: string;
  toc_text: string;
  sections: PlanSection[];
};

export type ChapterProfileGenerationJob = {
  id: number;
  document_id: number;
  task_id: number | null;
  status: string;
  total_sections: number;
  processed_sections: number;
  created_count: number;
  updated_count: number;
  failed_count: number;
  rule_only_count: number;
  celery_task_id: string | null;
  error_message: string | null;
  created_by: number | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
};

export type ChapterProfileGenerationJobList = {
  items: ChapterProfileGenerationJob[];
  total: number;
  page: number;
  page_size: number;
};

export type ChapterProfileGenerationItem = {
  id: number;
  job_id: number;
  document_id: number;
  section_id: number | null;
  section_title: string | null;
  section_path: string | null;
  status: string;
  profile_id: number | null;
  used_llm: boolean;
  confidence: number | null;
  message: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
};

export type ChapterProfileGenerationItemList = {
  items: ChapterProfileGenerationItem[];
  total: number;
  page: number;
  page_size: number;
};

export type PlanSection = {
  id: number;
  document_id: number;
  parent_id: number | null;
  level: number;
  title: string;
  section_no: string | null;
  content: string;
  sort_no: number;
  created_at: string;
  children: PlanSection[];
};

export const listSectionParseModes = async () => {
  const { data } = await apiClient.get<SectionParseModeItem[]>("/documents/section-parse-modes");
  return data;
};

export const uploadDocument = async (
  file: File,
  documentType: DocumentType = "template",
  options?: { sectionParseMode?: SectionParseMode },
) => {
  const form = new FormData();
  form.append("file", file);
  form.append("document_type", documentType);
  if (options?.sectionParseMode) {
    form.append("section_parse_mode", options.sectionParseMode);
  }
  const { data } = await apiClient.post<DocumentUploadResult>("/documents/upload", form);
  return data;
};

export const listDocuments = async (query?: { document_type?: DocumentType }) => {
  const { data } = await apiClient.get<DocumentRecord[]>("/documents", { params: query });
  return data;
};

export const deleteDocument = async (id: number) => {
  const { data } = await apiClient.delete<DocumentRecord>(`/documents/${id}`);
  return data;
};

export const parseDocument = async (id: number, sectionParseMode?: SectionParseMode) => {
  const { data } = await apiClient.post<DocumentParseResult>(`/documents/${id}/parse`, null, {
    params: sectionParseMode ? { section_parse_mode: sectionParseMode } : undefined,
  });
  return data;
};

export const getDocumentSections = async (id: number) => {
  const { data } = await apiClient.get<DocumentParseResult>(`/documents/${id}/sections`);
  return data;
};

export const createChapterProfileJob = async (documentId: number) => {
  const { data } = await apiClient.post<{ job: ChapterProfileGenerationJob }>(
    `/documents/${documentId}/chapter-profile-jobs`,
  );
  return data.job;
};

export const listChapterProfileJobs = async (query: {
  document_id?: number;
  status?: string;
  page?: number;
  page_size?: number;
} = {}) => {
  const { data } = await apiClient.get<ChapterProfileGenerationJobList>("/documents/chapter-profile-jobs", {
    params: query,
  });
  return data;
};

export const getChapterProfileJob = async (jobId: number) => {
  const { data } = await apiClient.get<ChapterProfileGenerationJob>(`/documents/chapter-profile-jobs/${jobId}`);
  return data;
};

export const listChapterProfileJobItems = async (
  jobId: number,
  query: { status?: string; page?: number; page_size?: number } = {},
) => {
  const { data } = await apiClient.get<ChapterProfileGenerationItemList>(
    `/documents/chapter-profile-jobs/${jobId}/items`,
    { params: query },
  );
  return data;
};
