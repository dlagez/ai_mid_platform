import { apiClient } from "./apiClient";

export type KnowledgeStatus = {
  kb_name: string;
  kb_dir: string;
  model: string;
  language: string;
  directories: Record<string, number>;
  total_indexed: number;
  last_compile?: string | null;
  last_lint?: string | null;
};

export type KnowledgeList = {
  kb_name: string;
  documents: Array<{
    hash: string;
    name: string;
    type: string;
    pages?: number | string | null;
  }>;
  summaries: string[];
  concepts: string[];
  reports: string[];
};

export type KnowledgeAddResult = {
  kb_name: string;
  added: string[];
  skipped: string[];
};

export type KnowledgeRawFile = {
  name: string;
  relative_path: string;
  path: string;
  size: number;
  modified_at: string;
  supported: boolean;
  indexed: boolean;
};

export type KnowledgeRawFiles = {
  kb_name: string;
  raw_dir: string;
  files: KnowledgeRawFile[];
};

export type KnowledgeUploadResult = {
  kb_name: string;
  filename: string;
  path: string;
  status: string;
};

export type KnowledgeQueryResult = {
  kb_name: string;
  question: string;
  answer: string;
  saved_path?: string | null;
};

export type KnowledgeChatResult = {
  kb_name: string;
  session_id: string;
  message: string;
  answer: string;
  turn_count: number;
};

export type KnowledgeCommand = {
  command: string;
  description: string;
};

export type KnowledgeClearResult = {
  kb_name: string;
  previous_session_id?: string | null;
  session_id: string;
  message: string;
};

export type KnowledgeSaveResult = {
  kb_name: string;
  session_id: string;
  saved_path: string;
  message: string;
};

export type KnowledgeLintResult = {
  kb_name: string;
  report_path?: string | null;
  message: string;
};

export type KnowledgeExitResult = {
  kb_name: string;
  session_id?: string | null;
  closed: boolean;
  message: string;
};

export const getKnowledgeStatus = async (kbName?: string) => {
  const { data } = await apiClient.get<KnowledgeStatus>("/knowledge/status", {
    params: { kb_name: kbName || undefined },
  });
  return data;
};

export const listKnowledge = async (kbName?: string) => {
  const { data } = await apiClient.get<KnowledgeList>("/knowledge/list", {
    params: { kb_name: kbName || undefined },
  });
  return data;
};

export const listKnowledgeFiles = async (kbName?: string) => {
  const { data } = await apiClient.get<KnowledgeRawFiles>("/knowledge/files", {
    params: { kb_name: kbName || undefined },
  });
  return data;
};

export const addKnowledgePath = async (payload: { kbName?: string; path: string }) => {
  const form = new FormData();
  if (payload.kbName) {
    form.append("kb_name", payload.kbName);
  }
  form.append("path", payload.path);
  const { data } = await apiClient.post<KnowledgeAddResult>("/knowledge/add", form);
  return data;
};

export const addKnowledgeFile = async (payload: { kbName?: string; file: File }) => {
  const form = new FormData();
  if (payload.kbName) {
    form.append("kb_name", payload.kbName);
  }
  form.append("file", payload.file);
  const { data } = await apiClient.post<KnowledgeAddResult>("/knowledge/add", form);
  return data;
};

export const uploadKnowledgeFile = async (payload: { kbName?: string; file: File }) => {
  const form = new FormData();
  if (payload.kbName) {
    form.append("kb_name", payload.kbName);
  }
  form.append("file", payload.file);
  const { data } = await apiClient.post<KnowledgeUploadResult>("/knowledge/upload", form);
  return data;
};

export const queryKnowledge = async (payload: { kbName?: string; question: string; save?: boolean }) => {
  const { data } = await apiClient.post<KnowledgeQueryResult>("/knowledge/query", {
    kb_name: payload.kbName || null,
    question: payload.question,
    save: payload.save ?? false,
  });
  return data;
};

export const chatKnowledge = async (payload: { kbName?: string; message: string; sessionId?: string }) => {
  const { data } = await apiClient.post<KnowledgeChatResult>("/knowledge/chat", {
    kb_name: payload.kbName || null,
    message: payload.message,
    session_id: payload.sessionId || null,
  });
  return data;
};

export const helpKnowledge = async () => {
  const { data } = await apiClient.get<{ commands: KnowledgeCommand[] }>("/knowledge/help");
  return data;
};

export const clearKnowledgeSession = async (payload: { kbName?: string; previousSessionId?: string }) => {
  const { data } = await apiClient.post<KnowledgeClearResult>("/knowledge/clear", {
    kb_name: payload.kbName || null,
    previous_session_id: payload.previousSessionId || null,
  });
  return data;
};

export const saveKnowledgeTranscript = async (payload: { kbName?: string; sessionId: string; name?: string }) => {
  const { data } = await apiClient.post<KnowledgeSaveResult>("/knowledge/save", {
    kb_name: payload.kbName || null,
    session_id: payload.sessionId,
    name: payload.name || null,
  });
  return data;
};

export const lintKnowledge = async (payload: { kbName?: string }) => {
  const { data } = await apiClient.post<KnowledgeLintResult>("/knowledge/lint", {
    kb_name: payload.kbName || null,
  });
  return data;
};

export const exitKnowledgeSession = async (payload: { kbName?: string; sessionId?: string }) => {
  const { data } = await apiClient.post<KnowledgeExitResult>("/knowledge/exit", {
    kb_name: payload.kbName || null,
    session_id: payload.sessionId || null,
  });
  return data;
};
