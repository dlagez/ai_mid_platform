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
