import type { DashboardStats } from "@/types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

export async function fetchDashboardStats(): Promise<DashboardStats> {
  const res = await fetch(`${BASE_URL}/api/dashboard/stats`);
  if (!res.ok) throw new Error(`Dashboard stats failed with status ${res.status}`);
  return res.json() as Promise<DashboardStats>;
}
