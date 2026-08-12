const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";

// The actual access/refresh tokens live only in HttpOnly cookies set by the
// backend (see backend/app/api/v1/auth.py) -- JS never touches them. This flag
// is just a UI hint so the router doesn't need a network round-trip to decide
// whether to show the login screen; the cookie is still the real source of
// truth and every request enforces it server-side regardless of this flag.
const LOGGED_IN_FLAG_KEY = "bmp_logged_in";

export function isLoggedIn(): boolean {
  return localStorage.getItem(LOGGED_IN_FLAG_KEY) === "1";
}

export function markLoggedIn() {
  localStorage.setItem(LOGGED_IN_FLAG_KEY, "1");
}

export function markLoggedOut() {
  localStorage.removeItem(LOGGED_IN_FLAG_KEY);
}

class ApiError extends Error {
  status: number;
  // Set when the backend's `detail` is a structured object rather than a
  // plain string -- currently only the OTP resend-cooldown 429 (see
  // backend/app/api/v1/auth.py) does this.
  retryAfterSeconds?: number;
  constructor(status: number, message: string, retryAfterSeconds?: number) {
    super(message);
    this.status = status;
    this.retryAfterSeconds = retryAfterSeconds;
  }
}

async function request<T>(path: string, options: RequestInit = {}, retry = true): Promise<T> {
  // FormData uploads must NOT get a manual Content-Type -- the browser sets
  // multipart/form-data with the correct boundary itself only when it owns
  // that header.
  const isFormData = options.body instanceof FormData;
  const headers: Record<string, string> = {
    ...(isFormData ? {} : { "Content-Type": "application/json" }),
    ...(options.headers as Record<string, string> | undefined),
  };

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
    credentials: "include",
  });

  if (response.status === 401 && retry) {
    const refreshed = await tryRefresh();
    if (refreshed) return request<T>(path, options, false);
    markLoggedOut();
  }

  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    const detail = body.detail;
    // FastAPI's own request-validation errors (422s from a malformed body --
    // not our HTTPException(detail=...) calls) put an *array* of
    // {loc, msg, type} objects in `detail`, which also satisfies
    // `typeof === "object"` and would otherwise silently fall through to the
    // generic "Request failed" below.
    if (Array.isArray(detail)) {
      const message = detail.map((e) => e?.msg).filter(Boolean).join(" ");
      throw new ApiError(response.status, message || "Solicitud inválida");
    }
    if (detail && typeof detail === "object") {
      throw new ApiError(response.status, detail.message || "Request failed", detail.retry_after_seconds);
    }
    throw new ApiError(response.status, detail || "Request failed");
  }

  if (response.status === 204) return undefined as T;
  return response.json();
}

// Photo endpoints return raw image bytes, not JSON -- kept separate from
// request() rather than overloading its return-type handling. Returns null on
// 404 (no photo / no access) so callers can treat "nothing to show" as a
// normal case instead of a thrown error.
async function requestBlob(path: string, retry = true): Promise<Blob | null> {
  const response = await fetch(`${API_BASE_URL}${path}`, { method: "GET", credentials: "include" });

  if (response.status === 401 && retry) {
    const refreshed = await tryRefresh();
    if (refreshed) return requestBlob(path, false);
    markLoggedOut();
  }

  if (response.status === 404) return null;
  if (!response.ok) throw new ApiError(response.status, "No se pudo cargar la imagen");
  return response.blob();
}

async function tryRefresh(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({}),
    });
    return response.ok;
  } catch {
    return false;
  }
}

export const api = {
  get: <T>(path: string) => request<T>(path, { method: "GET" }),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: JSON.stringify(body ?? {}) }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(body ?? {}) }),
  del: <T>(path: string) => request<T>(path, { method: "DELETE" }),
  upload: <T>(path: string, formData: FormData, method: "PUT" | "POST" = "PUT") =>
    request<T>(path, { method, body: formData }),
  getBlob: (path: string) => requestBlob(path),
};

export { ApiError };
