export type CurrentUser = {
  username: string;
  role: string;
  permissions: string[];
};

export type TaskStatus = "PENDING" | "STARTED" | "SUCCESS" | "FAILURE" | "RETRY" | string;
