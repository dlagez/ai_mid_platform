import { apiClient } from "./apiClient";

export type SectionParseMode = "docling_auto" | "docling_toc_outline" | "python_docx" | "word_native";

export type SectionParseModeItem = {
  mode: SectionParseMode;
  label: string;
  description: string;
};

/** 与后端 SECTION_PARSE_MODES 保持一致，页面直接选用，不依赖接口拉取 */
export const SECTION_PARSE_MODE_OPTIONS: SectionParseModeItem[] = [
  {
    mode: "docling_auto",
    label: "Docling 线性分章（原方案）",
    description: "Docling 转 Markdown，auto 策略线性扫描，不启用目录大纲。",
  },
  {
    mode: "docling_toc_outline",
    label: "Docling 目录大纲分章",
    description: "Docling 转 Markdown，识别目录/目次并与正文标题匹配后填充章节内容。",
  },
  {
    mode: "python_docx",
    label: "python-docx 分章",
    description: "使用 python-docx 读取 Word 段落和标题样式，跳过目录段落和目录区域。",
  },
  {
    mode: "word_native",
    label: "Word 原生分章",
    description: "直接解析 OOXML：Heading 样式与编号标题，跳过 TOC 样式段落。",
  },
];

export const getSectionParseModeLabel = (mode: string) =>
  SECTION_PARSE_MODE_OPTIONS.find((item) => item.mode === mode)?.label ?? mode;

export type DocumentRecord = {
  id: number;
  file_name: string;
  file_path: string;
  file_size: number;
  document_type: DocumentType;
  section_parse_mode: SectionParseMode;
  parse_status: string;
  parse_progress: number;
  parse_results: ParseResultSummary[];
  created_at: string;
};

export type DocumentType = "template" | "construction_plan";

export type DocumentUploadResult = {
  id: number;
  file_name: string;
  document_type: DocumentType;
  section_parse_mode: SectionParseMode;
  status: string;
  parse_progress: number;
};

export type DocumentParseResult = {
  id: number;
  file_name: string;
  parse_result_id: number | null;
  section_parse_mode: SectionParseMode;
  parse_status: string;
  parse_progress: number;
  toc_text: string;
  sections: PlanSection[];
};

export type ParseResultSummary = {
  id: number;
  document_id: number;
  section_parse_mode: SectionParseMode;
  parse_status: string;
  parse_progress: number;
  section_count: number;
  error_message: string | null;
  parsed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type ParseJobRecord = {
  id: number;
  document_id: number;
  file_name: string;
  parse_result_id: number | null;
  section_parse_mode: SectionParseMode;
  job_type: "parse" | "reparse";
  status: string;
  progress: number;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
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
  mentioned_parameters: string[];
  mentioned_methods: string[];
  mentioned_risks: string[];
  mentioned_standards: string[];
  expected_missing_objects: string[];
  summary: string | null;
  confidence: number | null;
  created_at: string;
  updated_at: string;
};

export type ChapterReviewProfileList = {
  items: ChapterReviewProfile[];
  total: number;
  page: number;
  page_size: number;
};

export type PlanSection = {
  id: number;
  document_id: number;
  parse_result_id: number;
  parent_id: number | null;
  level: number;
  title: string;
  section_no: string | null;
  content: string;
  sort_no: number;
  created_at: string;
  children: PlanSection[];
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

export const parseDocumentsBatch = async (payload: {
  document_ids: number[];
  section_parse_modes: SectionParseMode[];
  concurrency: number;
}) => {
  const { data } = await apiClient.post<{ jobs: ParseJobRecord[] }>("/documents/parse-jobs/batch", payload);
  return data.jobs;
};

export const listParseJobs = async (query?: { document_type?: DocumentType; limit?: number }) => {
  const { data } = await apiClient.get<ParseJobRecord[]>("/documents/parse-jobs/list", { params: query });
  return data;
};

export const getDocumentSections = async (id: number, sectionParseMode?: SectionParseMode) => {
  const { data } = await apiClient.get<DocumentParseResult>(`/documents/${id}/sections`, {
    params: sectionParseMode ? { section_parse_mode: sectionParseMode } : undefined,
  });
  return data;
};

export const createChapterProfileJob = async (documentId: number, sectionParseMode?: SectionParseMode) => {
  const { data } = await apiClient.post<{ job: ChapterProfileGenerationJob }>(
    `/documents/${documentId}/chapter-profile-jobs`,
    null,
    {
      params: sectionParseMode ? { section_parse_mode: sectionParseMode } : undefined,
    },
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

export const listChapterProfileJobProfiles = async (
  jobId: number,
  query: { page?: number; page_size?: number } = {},
) => {
  const { data } = await apiClient.get<ChapterReviewProfileList>(
    `/documents/chapter-profile-jobs/${jobId}/profiles`,
    { params: query },
  );
  return data;
};
