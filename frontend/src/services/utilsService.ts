import { apiClient } from "./apiClient";

export type UtilityParseRecord = {
  id: number;
  source_file_name: string;
  source_file_path: string;
  source_file_size: number;
  source_content_type: string | null;
  parsed_file_name: string | null;
  parsed_file_path: string | null;
  parsed_file_size: number | null;
  parser_provider: string;
  parse_status: string;
  parsed: boolean;
  error_message: string | null;
  created_by: string;
  created_at: string;
  completed_at: string | null;
};

export type PPOcrParseResult = {
  record: UtilityParseRecord;
  markdown: string;
};

export type PPOcrPdfJob = {
  id: number;
  file_id: string;
  file_name: string;
  file_size: number;
  file_hash: string;
  page_count: number;
  source_file_path: string;
  parser_provider: string;
  parse_mode: string;
  ocr_endpoint: string;
  status: string;
  dpi: number;
  batch_size: number;
  page_timeout_seconds: number;
  min_confidence: number;
  low_confidence_flag: boolean;
  total_pages: number;
  succeeded_pages: number;
  failed_pages: number;
  low_confidence_pages: number;
  avg_confidence: number | null;
  block_count: number;
  metadata: Record<string, unknown>;
  error_message: string | null;
  result_markdown_path: string | null;
  result_json_path: string | null;
  raw_result_path: string | null;
  created_by: string;
  created_at: string | null;
  started_at: string | null;
  completed_at: string | null;
};

export type PPOcrPdfPage = {
  id: number;
  job_id: number;
  page_no: number;
  status: string;
  image_path: string | null;
  raw_json_path: string | null;
  text: string;
  markdown_content: string;
  rec_texts: unknown[];
  rec_scores: unknown[];
  rec_polys: unknown[];
  average_confidence: number | null;
  min_confidence: number | null;
  block_count: number;
  low_confidence_flag: boolean;
  retry_count: number;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
};

export type PPOcrMarkdownMap = {
  id: number;
  job_id: number;
  page_result_id: number;
  page_no: number;
  markdown_start: number;
  markdown_end: number;
  anchor: string;
  block_count: number;
  created_at: string | null;
};

export type PPOcrPdfJobDetail = {
  job: PPOcrPdfJob;
  pages: PPOcrPdfPage[];
  markdown_maps: PPOcrMarkdownMap[];
};

export type PPOcrPdfMarkdownResult = {
  job: PPOcrPdfJob;
  markdown: string;
  markdown_maps: PPOcrMarkdownMap[];
};

export type PPOcrResultSection = {
  id: number;
  document_id: number;
  job_id: number;
  parent_id: number | null;
  title_level: number;
  title: string;
  section_no: string | null;
  content: string;
  sort_no: number;
  created_at: string | null;
  children: PPOcrResultSection[];
};

export type PPOcrResultSectionFlat = Omit<PPOcrResultSection, "children">;

export type PPOcrPdfSectionsResult = {
  job: PPOcrPdfJob;
  sections: PPOcrResultSection[];
  flat_sections: PPOcrResultSectionFlat[];
};

export type SectionRebuildStrategy = "markdown_heading" | "decimal_number" | "chinese_number" | "custom";

export type SectionRebuildRequest = {
  strategy: SectionRebuildStrategy;
  use_toc_outline: boolean;
  level1_pattern?: string | null;
  level2_pattern?: string | null;
  level3_pattern?: string | null;
};

export const parsePPOcrFile = async (file: File) => {
  const form = new FormData();
  form.append("file", file);
  const { data } = await apiClient.post<PPOcrParseResult>("/utils/ppocr/parse", form);
  return data;
};

export const listPPOcrRecords = async () => {
  const { data } = await apiClient.get<UtilityParseRecord[]>("/utils/ppocr/records");
  return data;
};

export const getPPOcrMarkdown = async (id: number) => {
  const { data } = await apiClient.get<PPOcrParseResult>(`/utils/ppocr/records/${id}/markdown`);
  return data;
};

export const createPPOcrPdfJob = async (file: File) => {
  const form = new FormData();
  form.append("file", file);
  const { data } = await apiClient.post<PPOcrPdfJob>("/utils/ppocr/pdf/jobs", form);
  return data;
};

export const listPPOcrPdfJobs = async () => {
  const { data } = await apiClient.get<PPOcrPdfJob[]>("/utils/ppocr/pdf/jobs");
  return data;
};

export const getPPOcrPdfJob = async (id: number) => {
  const { data } = await apiClient.get<PPOcrPdfJobDetail>(`/utils/ppocr/pdf/jobs/${id}`);
  return data;
};

export const getPPOcrPdfMarkdown = async (id: number) => {
  const { data } = await apiClient.get<PPOcrPdfMarkdownResult>(`/utils/ppocr/pdf/jobs/${id}/markdown`);
  return data;
};

export const getPPOcrPdfSections = async (id: number) => {
  const { data } = await apiClient.get<PPOcrPdfSectionsResult>(`/utils/ppocr/pdf/jobs/${id}/sections`);
  return data;
};

export const rebuildPPOcrPdfSections = async (id: number, request: SectionRebuildRequest) => {
  const { data } = await apiClient.post<PPOcrPdfSectionsResult>(`/utils/ppocr/pdf/jobs/${id}/sections/rebuild`, request);
  return data;
};

export const retryPPOcrPdfPage = async (jobId: number, pageNo: number) => {
  const { data } = await apiClient.post<PPOcrPdfPage>(`/utils/ppocr/pdf/jobs/${jobId}/pages/${pageNo}/retry`);
  return data;
};
