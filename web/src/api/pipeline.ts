import type { Pipeline, PipelineCreate, PipelineUpdate } from "@/types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

export async function listPipelines(): Promise<Pipeline[]> {
  const res = await fetch(`${BASE_URL}/api/pipelines`);
  if (!res.ok) {
    const body = await res
      .json()
      .catch(() => ({ detail: "Failed to list pipelines" }));
    throw new Error(body.detail ?? "Failed to list pipelines");
  }
  return res.json() as Promise<Pipeline[]>;
}

export async function createPipeline(req: PipelineCreate): Promise<Pipeline> {
  const res = await fetch(`${BASE_URL}/api/pipelines`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const body = await res
      .json()
      .catch(() => ({ detail: "Failed to create pipeline" }));
    throw new Error(body.detail ?? "Failed to create pipeline");
  }
  return res.json() as Promise<Pipeline>;
}

export async function updatePipeline(
  id: string,
  req: PipelineUpdate,
): Promise<Pipeline> {
  const res = await fetch(`${BASE_URL}/api/pipelines/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const body = await res
      .json()
      .catch(() => ({ detail: "Failed to update pipeline" }));
    throw new Error(body.detail ?? "Failed to update pipeline");
  }
  return res.json() as Promise<Pipeline>;
}

export async function deletePipeline(id: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/api/pipelines/${id}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    const body = await res
      .json()
      .catch(() => ({ detail: "Failed to delete pipeline" }));
    throw new Error(body.detail ?? "Failed to delete pipeline");
  }
}

export async function triggerPipeline(
  id: string,
): Promise<{ jobId: string }> {
  const res = await fetch(`${BASE_URL}/api/pipelines/${id}/trigger`, {
    method: "POST",
  });
  if (!res.ok) {
    const body = await res
      .json()
      .catch(() => ({ detail: "Failed to trigger pipeline" }));
    throw new Error(body.detail ?? "Failed to trigger pipeline");
  }
  return res.json() as Promise<{ jobId: string }>;
}

export async function togglePipeline(id: string): Promise<Pipeline> {
  const res = await fetch(`${BASE_URL}/api/pipelines/${id}/toggle`, {
    method: "POST",
  });
  if (!res.ok) {
    const body = await res
      .json()
      .catch(() => ({ detail: "Failed to toggle pipeline" }));
    throw new Error(body.detail ?? "Failed to toggle pipeline");
  }
  return res.json() as Promise<Pipeline>;
}
