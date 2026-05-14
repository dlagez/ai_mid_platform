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
