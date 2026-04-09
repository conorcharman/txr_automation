import type {
  JobResponse,
  FirdsRefreshRequest,
  FirdsCheckRequest,
  FirdsBackfillRequest,
  FirdsLookupResponse,
} from "@/types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    throw new Error(`Request failed with status ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export async function listFirdsScripts(): Promise<string[]> {
  const res = await fetch(`${BASE_URL}/api/firds/scripts`);
  return handleResponse<string[]>(res);
}

export async function firdsRefresh(req: FirdsRefreshRequest): Promise<JobResponse> {
  const res = await fetch(`${BASE_URL}/api/firds/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return handleResponse<JobResponse>(res);
}

export async function firdsCheck(req: FirdsCheckRequest): Promise<JobResponse> {
  const res = await fetch(`${BASE_URL}/api/firds/check`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return handleResponse<JobResponse>(res);
}

export async function firdsBackfill(req: FirdsBackfillRequest): Promise<JobResponse> {
  const res = await fetch(`${BASE_URL}/api/firds/backfill`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return handleResponse<JobResponse>(res);
}

export async function firdsLookup(
  isin: string,
  date: string,
  mic?: string,
): Promise<FirdsLookupResponse> {
  const params = new URLSearchParams({ isin, date });
  if (mic) params.set("mic", mic);
  const res = await fetch(`${BASE_URL}/api/firds/lookup?${params.toString()}`);
  return handleResponse<FirdsLookupResponse>(res);
}
