import type {
  JobResponse,
  ReplayPhase2FinalRequest,
  ReplayPhase2Request,
  ReplayPhase3Request,
  ReplayPhase3FinalRequest,
  ReplayMergeRequest,
} from "@/types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    throw new Error(`Request failed with status ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export async function listReplayScripts(): Promise<string[]> {
  const res = await fetch(`${BASE_URL}/api/replay/scripts`);
  return handleResponse<string[]>(res);
}

export async function runReplayPhase2(req: ReplayPhase2Request): Promise<JobResponse> {
  const res = await fetch(`${BASE_URL}/api/replay/phase2`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return handleResponse<JobResponse>(res);
}

export async function runReplayPhase2Final(req: ReplayPhase2FinalRequest): Promise<JobResponse> {
  const res = await fetch(`${BASE_URL}/api/replay/phase2-final`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return handleResponse<JobResponse>(res);
}

export async function runReplayPhase3(req: ReplayPhase3Request): Promise<JobResponse> {
  const res = await fetch(`${BASE_URL}/api/replay/phase3`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return handleResponse<JobResponse>(res);
}

export async function runReplayPhase3Final(req: ReplayPhase3FinalRequest): Promise<JobResponse> {
  const res = await fetch(`${BASE_URL}/api/replay/phase3-final`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return handleResponse<JobResponse>(res);
}

export async function runReplayMerge(req: ReplayMergeRequest): Promise<JobResponse> {
  const res = await fetch(`${BASE_URL}/api/replay/merge`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return handleResponse<JobResponse>(res);
}
