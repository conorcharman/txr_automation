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

export interface JobResponse {
  id: string;
  scriptName: string;
  status: JobStatus;
  createdAt: string;
  startedAt: string | null;
  completedAt: string | null;
  errorMessage: string | null;
  outputFiles: string[] | null;
}

export interface CreateJobRequest {
  scriptName: string;
  config: Record<string, unknown>;
}

export interface PaginatedJobs {
  items: JobResponse[];
  total: number;
}

export interface WsMessage {
  type: "log" | "status";
  data: string;
}
