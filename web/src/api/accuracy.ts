import type { JobResponse, RunValidationRequest, RunAllRequest, RunIncidentsRequest, DiscoveryRequest, DiscoveryResponse } from "@/types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    throw new Error(`Request failed with status ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export async function listAccuracyScripts(): Promise<string[]> {
  const res = await fetch(`${BASE_URL}/api/accuracy/scripts`);
  return handleResponse<string[]>(res);
}

export async function runValidation(req: RunValidationRequest): Promise<JobResponse> {
  const res = await fetch(`${BASE_URL}/api/accuracy/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return handleResponse<JobResponse>(res);
}

export async function runAllValidations(req: RunAllRequest): Promise<JobResponse> {
  const res = await fetch(`${BASE_URL}/api/accuracy/run-all`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return handleResponse<JobResponse>(res);
}

export async function runIncidents(req: RunIncidentsRequest): Promise<JobResponse> {
  const res = await fetch(`${BASE_URL}/api/accuracy/run-incidents`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return handleResponse<JobResponse>(res);
}

export async function discoverIncidents(req: DiscoveryRequest): Promise<DiscoveryResponse> {
  const res = await fetch(`${BASE_URL}/api/accuracy/discover`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return handleResponse<DiscoveryResponse>(res);
}
