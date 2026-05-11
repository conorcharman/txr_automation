import type { BrowseResponse, FileReadResponse, ResolvedPaths, ResolvePathsRequest } from "@/types";

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

export async function resolvePaths(
  req: ResolvePathsRequest,
): Promise<ResolvedPaths> {
  const res = await fetch(`${BASE_URL}/api/filesystem/resolve-paths`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const body = await res
      .json()
      .catch(() => ({ detail: "Path resolution failed" }));
    throw new Error(body.detail ?? "Path resolution failed");
  }
  return res.json() as Promise<ResolvedPaths>;
}

export async function readFile(path: string): Promise<FileReadResponse> {
  const res = await fetch(
    `${BASE_URL}/api/filesystem/read?path=${encodeURIComponent(path)}`,
  );
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "Read failed" }));
    throw new Error(body.detail ?? "Read failed");
  }
  return res.json() as Promise<FileReadResponse>;
}
