/** Minimal API client. The UI is never a security boundary — every
 *  sensitive operation is enforced server-side (see SECURITY.md). */

export interface HealthResponse {
  status: string;
}

export interface ReadyResponse {
  status: string;
  database: string;
}

/** Live state of the backend as seen by the browser. */
export type ApiState =
  | { kind: "checking" }
  | { kind: "ok"; database: string }
  | { kind: "error"; message: string };

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function getJson<T>(path: string, timeoutMs = 4000): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "GET",
    signal: AbortSignal.timeout(timeoutMs),
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`API ${path} responded ${response.status}`);
  }
  return (await response.json()) as T;
}

export function fetchHealth(): Promise<HealthResponse> {
  return getJson<HealthResponse>("/health");
}

export function fetchReady(): Promise<ReadyResponse> {
  return getJson<ReadyResponse>("/ready");
}

/** Never throws: folds readiness into a UI-friendly state object. */
export async function loadApiState(): Promise<ApiState> {
  try {
    const ready = await fetchReady();
    return { kind: "ok", database: ready.database };
  } catch (error: unknown) {
    const message =
      error instanceof Error ? error.message : "неизвестная ошибка";
    return { kind: "error", message };
  }
}
