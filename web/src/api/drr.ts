import type {
  DRRBulkComplianceCheckResponse,
  DRRCdmReportResponse,
  DRRComplianceCheckRequest,
  DRRComplianceCheckResponse,
  DRRRuleCatalogueEntry,
  DRRSubmissionSummary,
} from "@/types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Request failed with status ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export async function listDRRRules(): Promise<DRRRuleCatalogueEntry[]> {
  const res = await fetch(`${BASE_URL}/api/drr/rules`);
  return handleResponse<DRRRuleCatalogueEntry[]>(res);
}

export async function runComplianceCheck(
  req: DRRComplianceCheckRequest
): Promise<DRRComplianceCheckResponse> {
  const res = await fetch(`${BASE_URL}/api/drr/compliance-check`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return handleResponse<DRRComplianceCheckResponse>(res);
}

export async function runCdmReport(
  req: DRRComplianceCheckRequest
): Promise<DRRCdmReportResponse> {
  const res = await fetch(`${BASE_URL}/api/drr/cdm-report`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return handleResponse<DRRCdmReportResponse>(res);
}

export async function runBulkComplianceCheck(
  file: File
): Promise<DRRBulkComplianceCheckResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${BASE_URL}/api/drr/compliance-check/bulk`, {
    method: "POST",
    body: formData,
  });
  return handleResponse<DRRBulkComplianceCheckResponse>(res);
}

export async function listDRRSubmissions(): Promise<DRRSubmissionSummary[]> {
  const res = await fetch(`${BASE_URL}/api/drr/submissions`);
  return handleResponse<DRRSubmissionSummary[]>(res);
}

export async function getDRRSubmission(
  id: string
): Promise<DRRComplianceCheckResponse> {
  const res = await fetch(`${BASE_URL}/api/drr/submissions/${id}`);
  return handleResponse<DRRComplianceCheckResponse>(res);
}
