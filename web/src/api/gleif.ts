import type {
  JobResponse,
  GleifRefreshRequest,
  GleifCheckRequest,
  GleifBackfillRequest,
} from "@/types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    throw new Error(`Request failed with status ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export async function listGleifScripts(): Promise<string[]> {
  const res = await fetch(`${BASE_URL}/api/gleif/scripts`);
  return handleResponse<string[]>(res);
}

export async function gleifRefresh(req: GleifRefreshRequest): Promise<JobResponse> {
  const res = await fetch(`${BASE_URL}/api/gleif/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return handleResponse<JobResponse>(res);
}

export async function gleifCheck(req: GleifCheckRequest): Promise<JobResponse> {
  const res = await fetch(`${BASE_URL}/api/gleif/check`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return handleResponse<JobResponse>(res);
}

export async function gleifBackfill(req: GleifBackfillRequest): Promise<JobResponse> {
  const res = await fetch(`${BASE_URL}/api/gleif/backfill`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return handleResponse<JobResponse>(res);
}
