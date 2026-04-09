import type {
  SavedConfigResponse,
  SavedConfigCreate,
  SavedConfigUpdate,
} from "@/types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`Request failed with status ${res.status}`);
  return res.json() as Promise<T>;
}

export async function listConfigs(
  scriptName?: string,
): Promise<SavedConfigResponse[]> {
  const params = scriptName
    ? `?script_name=${encodeURIComponent(scriptName)}`
    : "";
  const res = await fetch(`${BASE_URL}/api/configs${params}`);
  return handleResponse<SavedConfigResponse[]>(res);
}

export async function getConfig(configId: string): Promise<SavedConfigResponse> {
  const res = await fetch(
    `${BASE_URL}/api/configs/${encodeURIComponent(configId)}`,
  );
  return handleResponse<SavedConfigResponse>(res);
}

export async function createConfig(
  req: SavedConfigCreate,
): Promise<SavedConfigResponse> {
  const res = await fetch(`${BASE_URL}/api/configs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return handleResponse<SavedConfigResponse>(res);
}

export async function updateConfig(
  configId: string,
  req: SavedConfigUpdate,
): Promise<SavedConfigResponse> {
  const res = await fetch(
    `${BASE_URL}/api/configs/${encodeURIComponent(configId)}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
    },
  );
  return handleResponse<SavedConfigResponse>(res);
}

export async function deleteConfig(configId: string): Promise<void> {
  const res = await fetch(
    `${BASE_URL}/api/configs/${encodeURIComponent(configId)}`,
    { method: "DELETE" },
  );
  if (!res.ok)
    throw new Error(`Delete config failed with status ${res.status}`);
}
