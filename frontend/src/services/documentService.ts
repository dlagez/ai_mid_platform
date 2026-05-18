import { apiClient } from "./apiClient";

export type DocumentRecord = {
  id: number;
  file_name: string;
  file_path: string;
  file_size: number;
  parse_status: string;
  created_at: string;
};

export type DocumentUploadResult = {
  id: number;
  file_name: string;
  status: string;
};

export type DocumentParseResult = {
  id: number;
  file_name: string;
  parse_status: string;
  toc_text: string;
  sections: PlanSection[];
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

export const uploadDocument = async (file: File) => {
  const form = new FormData();
  form.append("file", file);
  const { data } = await apiClient.post<DocumentUploadResult>("/documents/upload", form);
  return data;
};

export const listDocuments = async () => {
  const { data } = await apiClient.get<DocumentRecord[]>("/documents");
  return data;
};

export const parseDocument = async (id: number) => {
  const { data } = await apiClient.post<DocumentParseResult>(`/documents/${id}/parse`);
  return data;
};

export const getDocumentSections = async (id: number) => {
  const { data } = await apiClient.get<DocumentParseResult>(`/documents/${id}/sections`);
  return data;
};
