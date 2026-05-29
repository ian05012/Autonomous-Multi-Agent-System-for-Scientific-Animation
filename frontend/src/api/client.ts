import type { ApiState, PipelineStartPayload, ProgressState } from "../types/pipeline";

export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: init?.body instanceof FormData ? undefined : { "Content-Type": "application/json" },
    ...init,
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail ?? `Request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export const api = {
  getState: () => request<ApiState>("/api/state"),
  getProgress: () => request<ProgressState>("/api/progress"),
  startPipeline: (payload: PipelineStartPayload) =>
    request<ApiState>("/api/pipeline/start", { method: "POST", body: JSON.stringify(payload) }),
  uploadPdf: async (file: File) => {
    const data = new FormData();
    data.append("file", file);
    return request<{ path: string; filename: string }>("/api/upload/pdf", { method: "POST", body: data });
  },
  submitRevision: (revision_text: string) =>
    request<ApiState>("/api/revision", { method: "POST", body: JSON.stringify({ revision_text }) }),
  composeVideo: (subtitle_enabled: boolean, subtitle_language: string) =>
    request<ApiState>("/api/video/compose", {
      method: "POST",
      body: JSON.stringify({ subtitle_enabled, subtitle_language }),
    }),
  publish: () => request<ApiState>("/api/publish", { method: "POST" }),
  clear: () => request<ApiState>("/api/clear", { method: "POST" }),
};
