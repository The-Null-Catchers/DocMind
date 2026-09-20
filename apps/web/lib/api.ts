export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export type ApiError = { error?: { code?: string; message?: string }; detail?: string | object };

type AuthResponse = { access_token: string; refresh_token: string };
let refreshPromise: Promise<boolean> | null = null;

function token(key: string) {
  return typeof window !== "undefined" ? localStorage.getItem(key) : null;
}

function clearSession() {
  if (typeof window === "undefined") return;
  localStorage.removeItem("docmind_access_token");
  localStorage.removeItem("docmind_refresh_token");
}

async function refreshSession(): Promise<boolean> {
  if (refreshPromise) return refreshPromise;
  refreshPromise = (async () => {
    const refresh = token("docmind_refresh_token");
    if (!refresh) return false;
    try {
      const response = await fetch(`${API_URL}/auth/refresh`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ refresh_token: refresh }),
        cache: "no-store",
      });
      if (!response.ok) {
        clearSession();
        return false;
      }
      const next = (await response.json()) as AuthResponse;
      localStorage.setItem("docmind_access_token", next.access_token);
      localStorage.setItem("docmind_refresh_token", next.refresh_token);
      return true;
    } catch {
      return false;
    }
  })();
  try {
    return await refreshPromise;
  } finally {
    refreshPromise = null;
  }
}

async function request(path: string, init: RequestInit, retried: boolean): Promise<Response> {
  const headers = new Headers(init.headers);
  if (!(init.body instanceof FormData)) headers.set("content-type", "application/json");
  const access = token("docmind_access_token");
  if (access) headers.set("authorization", `Bearer ${access}`);
  const response = await fetch(`${API_URL}${path}`, { ...init, headers, cache: "no-store" });

  const isAuthRoute = path.startsWith("/auth/login") || path.startsWith("/auth/register") || path.startsWith("/auth/refresh");
  if (response.status === 401 && !retried && !isAuthRoute && (await refreshSession())) {
    return request(path, init, true);
  }
  if (response.status === 401 && !isAuthRoute) clearSession();
  return response;
}

export async function apiResponse(path: string, init: RequestInit = {}): Promise<Response> {
  const response = await request(path, init, false);
  if (!response.ok) {
    const body = (await response.clone().json().catch(() => ({}))) as ApiError;
    const detail = body.detail;
    const message =
      typeof detail === "string"
        ? detail
        : typeof detail === "object" && detail && "message" in detail && typeof detail.message === "string"
          ? detail.message
          : `Request failed (${response.status})`;
    throw new Error(message);
  }
  return response;
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await apiResponse(path, init);
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function apiBlob(path: string): Promise<Blob> {
  const response = await apiResponse(path, { headers: { accept: "*/*" } });
  return response.blob();
}

export function storeSession(result: AuthResponse) {
  localStorage.setItem("docmind_access_token", result.access_token);
  localStorage.setItem("docmind_refresh_token", result.refresh_token);
}

export function logoutLocal() {
  clearSession();
}
