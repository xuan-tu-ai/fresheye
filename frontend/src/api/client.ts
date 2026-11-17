import type { Action, HealthOut, ImageUploadOut, InspectionOut, StatsOut } from "./types";

/** An HTTP error from the backend, keeping the status so screens can branch on it. */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = typeof body?.detail === "string" ? body.detail : response.statusText;
    throw new ApiError(response.status, detail);
  }
  return (await response.json()) as T;
}

export function getHealth(): Promise<HealthOut> {
  return request<HealthOut>("/api/health");
}

export function createInspection(): Promise<InspectionOut> {
  return request<InspectionOut>("/api/inspections", { method: "POST" });
}

/** Upload one square eye crop; the response carries the merged decision for the inspection. */
export function uploadImage(inspectionId: number, crop: Blob): Promise<ImageUploadOut> {
  const form = new FormData();
  form.append("file", crop, "eye.jpg");
  return request<ImageUploadOut>(`/api/inspections/${inspectionId}/images`, {
    method: "POST",
    body: form,
  });
}

/** Stop an open inspection without a conclusion; a closed one answers 409. */
export function closeInspection(inspectionId: number): Promise<InspectionOut> {
  return request<InspectionOut>(`/api/inspections/${inspectionId}/close`, { method: "POST" });
}

export function getInspection(inspectionId: number): Promise<InspectionOut> {
  return request<InspectionOut>(`/api/inspections/${inspectionId}`);
}

/** Newest first. `action` keeps only inspections with that decision. */
export function listInspections(
  limit = 20,
  offset = 0,
  action: Action | null = null,
): Promise<InspectionOut[]> {
  const filter = action ? `&action=${action}` : "";
  return request<InspectionOut[]>(`/api/inspections?limit=${limit}&offset=${offset}${filter}`);
}

/** Dashboard counts; `days` keeps only inspections from the last that many days. */
export function getStats(days: number | null = null): Promise<StatsOut> {
  return request<StatsOut>(days ? `/api/stats?days=${days}` : "/api/stats");
}

/**
 * Run one assistant turn and report its text as it arrives (server-sent events).
 * `kind: "explain"` asks for the explanation of the current result; `"user"` sends `message`.
 */
export async function streamChat(
  inspectionId: number,
  body: { kind: "explain" | "user"; message?: string },
  onText: (chunk: string) => void,
): Promise<void> {
  const response = await fetch(`/api/inspections/${inspectionId}/chat`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok || !response.body) throw new ApiError(response.status, response.statusText);

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) return;
    buffer += value;
    const events = buffer.split("\n\n");
    buffer = events.pop() ?? "";
    for (const event of events) {
      if (!event.startsWith("data: ")) continue;
      const data = JSON.parse(event.slice(6)) as { text?: string; done?: boolean };
      if (data.done) return;
      if (data.text) onText(data.text);
    }
  }
}
