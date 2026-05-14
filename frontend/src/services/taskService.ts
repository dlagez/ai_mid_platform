import { apiClient } from "./apiClient";

export type TaskCreatePayload = {
  task_type: string;
  payload: Record<string, unknown>;
};

export const createTask = async (payload: TaskCreatePayload) => {
  const { data } = await apiClient.post("/tasks", payload);
  return data;
};

export const getTask = async (taskId: string) => {
  const { data } = await apiClient.get(`/tasks/${taskId}`);
  return data;
};
