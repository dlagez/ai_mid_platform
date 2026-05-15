import { apiClient } from "./apiClient";

export type DocumentRecord = {
  id: number;
  file_name: string;
  minio_path: string;
  uploaded_by: string;
  uploaded_at: string;
};

export type DocumentUploadResult = {
  id: number;
  file_name: string;
  status: string;
};

export type DocumentParseResult = {
  id: number;
  file_name: string;
  toc_text: string;
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
