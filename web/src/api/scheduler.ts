import type {
  Schedule,
  ScheduleCreate,
  ScheduleUpdate,
  ScheduleTriggerResponse,
} from "@/types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(body || `Request failed with status ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export async function listSchedules(): Promise<Schedule[]> {
  const res = await fetch(`${BASE_URL}/api/schedules`);
  return handleResponse<Schedule[]>(res);
}

export async function getSchedule(scheduleId: string): Promise<Schedule> {
  const res = await fetch(
    `${BASE_URL}/api/schedules/${encodeURIComponent(scheduleId)}`,
  );
  return handleResponse<Schedule>(res);
}

export async function createSchedule(req: ScheduleCreate): Promise<Schedule> {
  const res = await fetch(`${BASE_URL}/api/schedules`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return handleResponse<Schedule>(res);
}

export async function updateSchedule(
  scheduleId: string,
  req: ScheduleUpdate,
): Promise<Schedule> {
  const res = await fetch(
    `${BASE_URL}/api/schedules/${encodeURIComponent(scheduleId)}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
    },
  );
  return handleResponse<Schedule>(res);
}

export async function deleteSchedule(scheduleId: string): Promise<void> {
  const res = await fetch(
    `${BASE_URL}/api/schedules/${encodeURIComponent(scheduleId)}`,
    { method: "DELETE" },
  );
  if (!res.ok && res.status !== 204) {
    const body = await res.text().catch(() => "");
    throw new Error(body || `Request failed with status ${res.status}`);
  }
}

export async function triggerSchedule(
  scheduleId: string,
): Promise<ScheduleTriggerResponse> {
  const res = await fetch(
    `${BASE_URL}/api/schedules/${encodeURIComponent(scheduleId)}/trigger`,
    { method: "POST" },
  );
  return handleResponse<ScheduleTriggerResponse>(res);
}

export async function toggleSchedule(scheduleId: string): Promise<Schedule> {
  const res = await fetch(
    `${BASE_URL}/api/schedules/${encodeURIComponent(scheduleId)}/toggle`,
    { method: "POST" },
  );
  return handleResponse<Schedule>(res);
}
