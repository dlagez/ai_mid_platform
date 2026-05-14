import { Tag } from "antd";
import type { TaskStatus } from "../types/platform";

const statusColor: Record<string, string> = {
  PENDING: "gold",
  STARTED: "blue",
  SUCCESS: "green",
  FAILURE: "red",
  RETRY: "purple",
};

export const StatusTag = ({ status }: { status: TaskStatus }) => {
  return <Tag color={statusColor[status] ?? "default"}>{status}</Tag>;
};
