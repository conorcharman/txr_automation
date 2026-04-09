import type { BrowseResponse } from "@/types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

export async function browseDirectory(path: string): Promise<BrowseResponse> {
  const res = await fetch(
    `${BASE_URL}/api/filesystem/browse?path=${encodeURIComponent(path)}`,
  );
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "Browse failed" }));
    throw new Error(body.detail ?? "Browse failed");
  }
  return res.json() as Promise<BrowseResponse>;
}
