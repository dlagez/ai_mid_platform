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
