import type {
  JobResponse,
  GleifRefreshRequest,
  GleifCheckRequest,
  GleifBackfillRequest,
  GleifLookupResponse,
  GleifSearchResponse,
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

export async function gleifLookup(
  lei: string,
  date?: string,
): Promise<GleifLookupResponse> {
  const params = new URLSearchParams({ lei });
  if (date) params.set("date", date);
  const res = await fetch(`${BASE_URL}/api/gleif/lookup?${params.toString()}`);
  return handleResponse<GleifLookupResponse>(res);
}

export async function gleifSearch(
  name: string,
  limit = 20,
): Promise<GleifSearchResponse> {
  const params = new URLSearchParams({ name, limit: String(limit) });
  const res = await fetch(`${BASE_URL}/api/gleif/search?${params.toString()}`);
  return handleResponse<GleifSearchResponse>(res);
}
