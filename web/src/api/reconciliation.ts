import type {
  ReconciliationSchedule,
  ReconciliationScheduleCreate,
  ReconciliationScheduleUpdate,
} from "@/types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(body || `Request failed with status ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export async function listReconciliations(): Promise<ReconciliationSchedule[]> {
  const res = await fetch(`${BASE_URL}/api/reconciliations`);
  return handleResponse<ReconciliationSchedule[]>(res);
}

export async function getReconciliation(
  id: string,
): Promise<ReconciliationSchedule> {
  const res = await fetch(
    `${BASE_URL}/api/reconciliations/${encodeURIComponent(id)}`,
  );
  return handleResponse<ReconciliationSchedule>(res);
}

export async function createReconciliation(
  req: ReconciliationScheduleCreate,
): Promise<ReconciliationSchedule> {
  const res = await fetch(`${BASE_URL}/api/reconciliations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return handleResponse<ReconciliationSchedule>(res);
}

export async function updateReconciliation(
  id: string,
  req: ReconciliationScheduleUpdate,
): Promise<ReconciliationSchedule> {
  const res = await fetch(
    `${BASE_URL}/api/reconciliations/${encodeURIComponent(id)}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
    },
  );
  return handleResponse<ReconciliationSchedule>(res);
}

export async function deleteReconciliation(id: string): Promise<void> {
  const res = await fetch(
    `${BASE_URL}/api/reconciliations/${encodeURIComponent(id)}`,
    { method: "DELETE" },
  );
  if (!res.ok && res.status !== 204) {
    const body = await res.text().catch(() => "");
    throw new Error(body || `Request failed with status ${res.status}`);
  }
}

export async function triggerReconciliation(
  id: string,
): Promise<{ jobId: string }> {
  const res = await fetch(
    `${BASE_URL}/api/reconciliations/${encodeURIComponent(id)}/trigger`,
    { method: "POST" },
  );
  return handleResponse<{ jobId: string }>(res);
}

export async function toggleReconciliation(
  id: string,
): Promise<ReconciliationSchedule> {
  const res = await fetch(
    `${BASE_URL}/api/reconciliations/${encodeURIComponent(id)}/toggle`,
    { method: "POST" },
  );
  return handleResponse<ReconciliationSchedule>(res);
}
