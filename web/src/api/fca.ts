import type {
  FcaCheckRequest,
  FcaLeiSearchResponse,
  FcaLookupResponse,
  FcaSearchResponse,
} from "@/types";
import type { JobResponse } from "@/types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    throw new Error(`Request failed with status ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export async function fcaLookup(frn: string): Promise<FcaLookupResponse> {
  const params = new URLSearchParams({ frn });
  const res = await fetch(`${BASE_URL}/api/fca/lookup?${params.toString()}`);
  return handleResponse<FcaLookupResponse>(res);
}

export async function fcaSearch(name: string): Promise<FcaSearchResponse> {
  const params = new URLSearchParams({ name });
  const res = await fetch(`${BASE_URL}/api/fca/search?${params.toString()}`);
  return handleResponse<FcaSearchResponse>(res);
}

export async function fcaCheck(req: FcaCheckRequest): Promise<JobResponse> {
  const res = await fetch(`${BASE_URL}/api/fca/check`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return handleResponse<JobResponse>(res);
}

export async function fcaLookupByLei(lei: string): Promise<FcaLeiSearchResponse> {
  const params = new URLSearchParams({ lei });
  const res = await fetch(`${BASE_URL}/api/fca/lookup-by-lei?${params.toString()}`);
  return handleResponse<FcaLeiSearchResponse>(res);
}
