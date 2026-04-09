import type { JobResponse, CreateJobRequest, LastRunInfo } from "@/types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    throw new Error(`Request failed with status ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export async function listJobs(limit = 50, offset = 0): Promise<JobResponse[]> {
  const res = await fetch(`${BASE_URL}/api/jobs?limit=${limit}&offset=${offset}`);
  return handleResponse<JobResponse[]>(res);
}

export async function getJob(jobId: string): Promise<JobResponse> {
  const res = await fetch(`${BASE_URL}/api/jobs/${encodeURIComponent(jobId)}`);
  return handleResponse<JobResponse>(res);
}

export async function createJob(req: CreateJobRequest): Promise<JobResponse> {
  const res = await fetch(`${BASE_URL}/api/jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return handleResponse<JobResponse>(res);
}

export async function cancelJob(jobId: string): Promise<JobResponse> {
  const res = await fetch(`${BASE_URL}/api/jobs/${encodeURIComponent(jobId)}/cancel`, {
    method: "POST",
  });
  return handleResponse<JobResponse>(res);
}

export async function fetchLastRuns(): Promise<Record<string, LastRunInfo>> {
  const res = await fetch(`${BASE_URL}/api/jobs/last-runs`);
  return handleResponse<Record<string, LastRunInfo>>(res);
}
