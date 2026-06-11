/**
 * Daily Reconciliation API Client
 * ================================
 *
 * TypeScript API functions for daily_recon endpoints.
 * All functions use TanStack Query hooks (useQuery, useMutation).
 */

import type {
  CellCorrectionRequest,
  DailyReconRun,
  DailyReconTriggerRequest,
  DailyReconCell,
  DailyReconRow,
  PaginatedDailyReconRuns,
  PaginatedDailyReconRows,
} from "@/types";

const API_BASE = "/api/daily-recon";

// ──────────────────────────────────────────────────────────────────────────
// Runs
// ──────────────────────────────────────────────────────────────────────────

/**
 * Fetch paginated list of reconciliation runs.
 */
export async function listRuns(
  limit: number = 50,
  offset: number = 0
): Promise<PaginatedDailyReconRuns> {
  const response = await fetch(
    `${API_BASE}/runs?limit=${limit}&offset=${offset}`,
    { method: "GET" }
  );
  if (!response.ok) throw new Error(`Failed to fetch runs: ${response.statusText}`);
  return response.json();
}

/**
 * Fetch a single run with all rows and cells.
 */
export async function getRun(runId: string): Promise<DailyReconRun> {
  const response = await fetch(`${API_BASE}/runs/${runId}`, { method: "GET" });
  if (!response.ok) throw new Error(`Failed to fetch run: ${response.statusText}`);
  return response.json();
}

/**
 * Trigger a new daily reconciliation run.
 */
export async function triggerRun(
  req: DailyReconTriggerRequest
): Promise<DailyReconRun> {
  const response = await fetch(`${API_BASE}/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!response.ok) throw new Error(`Failed to trigger run: ${response.statusText}`);
  return response.json();
}

// ──────────────────────────────────────────────────────────────────────────
// Rows
// ──────────────────────────────────────────────────────────────────────────

/**
 * Fetch paginated rows for a run.
 */
export async function listRows(
  runId: string,
  limit: number = 50,
  offset: number = 0,
  erroredOnly: boolean = false
): Promise<PaginatedDailyReconRows> {
  const query = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
    errored_only: String(erroredOnly),
  });
  const response = await fetch(`${API_BASE}/runs/${runId}/rows?${query}`, {
    method: "GET",
  });
  if (!response.ok) throw new Error(`Failed to fetch rows: ${response.statusText}`);
  return response.json();
}

/**
 * Fetch a single row with all cells and issues.
 */
export async function getRow(rowId: string): Promise<DailyReconRow> {
  const response = await fetch(`${API_BASE}/rows/${rowId}`, { method: "GET" });
  if (!response.ok) throw new Error(`Failed to fetch row: ${response.statusText}`);
  return response.json();
}

/**
 * Mark a row as approved.
 */
export async function approveRow(rowId: string): Promise<DailyReconRow> {
  const response = await fetch(`${API_BASE}/rows/${rowId}/approve`, {
    method: "POST",
  });
  if (!response.ok) throw new Error(`Failed to approve row: ${response.statusText}`);
  return response.json();
}

/**
 * Unmark a row as approved.
 */
export async function unapproveRow(rowId: string): Promise<DailyReconRow> {
  const response = await fetch(`${API_BASE}/rows/${rowId}/unapprove`, {
    method: "POST",
  });
  if (!response.ok) throw new Error(`Failed to unapprove row: ${response.statusText}`);
  return response.json();
}

// ──────────────────────────────────────────────────────────────────────────
// Cells
// ──────────────────────────────────────────────────────────────────────────

/**
 * Fetch a single cell with issues.
 */
export async function getCell(cellId: number): Promise<DailyReconCell> {
  const response = await fetch(`${API_BASE}/cells/${cellId}`, { method: "GET" });
  if (!response.ok) throw new Error(`Failed to fetch cell: ${response.statusText}`);
  return response.json();
}

/**
 * Apply a manual correction to a cell.
 */
export async function applyCorrection(
  cellId: number,
  req: CellCorrectionRequest
): Promise<DailyReconCell> {
  const response = await fetch(`${API_BASE}/cells/${cellId}/correct`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!response.ok) throw new Error(`Failed to apply correction: ${response.statusText}`);
  return response.json();
}

/**
 * Accept a suggested fix for a cell.
 */
export async function acceptSuggestion(cellId: number): Promise<DailyReconCell> {
  const response = await fetch(`${API_BASE}/cells/${cellId}/accept-suggestion`, {
    method: "POST",
  });
  if (!response.ok) throw new Error(`Failed to accept suggestion: ${response.statusText}`);
  return response.json();
}

// ──────────────────────────────────────────────────────────────────────────
// Export
// ──────────────────────────────────────────────────────────────────────────

/**
 * Export approved rows as CSV.
 * Returns a Blob that can be downloaded as a file.
 */
export async function exportRun(runId: string): Promise<Blob> {
  const response = await fetch(`${API_BASE}/runs/${runId}/export`, {
    method: "GET",
  });
  if (!response.ok) throw new Error(`Failed to export run: ${response.statusText}`);
  return response.blob();
}


