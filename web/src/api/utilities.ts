import type { JobResponse, XlsxConverterRequest, XmlConverterRequest } from "@/types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    throw new Error(`Request failed with status ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export async function listUtilityScripts(): Promise<string[]> {
  const res = await fetch(`${BASE_URL}/api/utilities/scripts`);
  return handleResponse<string[]>(res);
}

export async function xlsxConvert(req: XlsxConverterRequest): Promise<JobResponse> {
  const res = await fetch(`${BASE_URL}/api/utilities/xlsx-convert`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return handleResponse<JobResponse>(res);
}

export async function xmlConvert(req: XmlConverterRequest): Promise<JobResponse> {
  const res = await fetch(`${BASE_URL}/api/utilities/xml-convert`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return handleResponse<JobResponse>(res);
}
