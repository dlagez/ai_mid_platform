import { apiClient } from "./apiClient";

export type ModelMessage = {
  role: "system" | "user" | "assistant";
  content: string;
};

export type ModelCallPayload = {
  model: string;
  messages: ModelMessage[];
  temperature: number;
  max_tokens?: number;
};

export const callModel = async (payload: ModelCallPayload) => {
  const { data } = await apiClient.post("/models/call", payload);
  return data;
};

export type PromptTestPayload = {
  prompt_type: "profile_extraction" | "checkpoint";
  text: string;
  model?: string;
  temperature: number;
  max_tokens?: number;
  title?: string;
  standard_name?: string;
  clause_no?: string;
  clause_title?: string;
};

export const testPrompt = async (payload: PromptTestPayload) => {
  const { data } = await apiClient.post("/models/prompt-test", payload);
  return data;
};

export type PromptTestRecord = {
  id: number;
  prompt_type: "profile_extraction" | "checkpoint";
  model: string;
  provider: string | null;
  temperature: number;
  max_tokens: number | null;
  input_text: string;
  rendered_prompt: string;
  output: unknown;
  status: "running" | "success" | "failed";
  error_message: string | null;
  created_by: string | null;
  created_at: string;
  completed_at: string | null;
};

export type PromptTestRecordQuery = {
  prompt_type?: "profile_extraction" | "checkpoint";
  status?: string;
  page?: number;
  page_size?: number;
};

export const listPromptTestRecords = async (query: PromptTestRecordQuery = {}) => {
  const { data } = await apiClient.get("/models/prompt-test-records", { params: query });
  return data as { items: PromptTestRecord[]; total: number; page: number; page_size: number };
};
