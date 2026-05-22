import { apiClient } from "./apiClient";

export type DocumentRecord = {
  id: number;
  file_name: string;
  file_path: string;
  file_size: number;
  document_type: DocumentType;
  parse_status: string;
  created_at: string;
};

export type DocumentType = "template" | "construction_plan";

export type DocumentUploadResult = {
  id: number;
  file_name: string;
  document_type: DocumentType;
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

export const uploadDocument = async (file: File, documentType: DocumentType = "template") => {
  const form = new FormData();
  form.append("file", file);
  form.append("document_type", documentType);
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

export const parseDocument = async (id: number) => {
  const { data } = await apiClient.post<DocumentParseResult>(`/documents/${id}/parse`);
  return data;
};

export const getDocumentSections = async (id: number) => {
  const { data } = await apiClient.get<DocumentParseResult>(`/documents/${id}/sections`);
  return data;
};
