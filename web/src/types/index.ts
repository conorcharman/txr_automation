export interface HealthResponse {
  status: string;
  version: string;
}

export type JobStatus = "pending" | "running" | "success" | "failed" | "cancelled";

export interface Job {
  id: string;
  scriptName: string;
  status: JobStatus;
  createdAt: string;
  startedAt: string | null;
  completedAt: string | null;
  errorMessage: string | null;
}

export interface WsMessage {
  type: "log" | "status";
  data: string;
}
