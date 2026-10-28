import axios from "axios";

/** API origin. Same-origin deployments (nginx proxying /api) can leave it empty. */
export const API_BASE = (
  import.meta.env.VITE_API_URL ||
  (import.meta.env.DEV ? "http://localhost:8000" : "")
).replace(/\/+$/, "");

export function wsUrl(path: string): string {
  const base = API_BASE || window.location.origin;
  return base.replace(/^http/, "ws") + path;
}
export const WS_BASE = (API_BASE || "").replace(/^http/, "ws");

const CSRF_COOKIE = "qf_csrf";
let csrfToken: string | null = null;

/** Remember the CSRF token returned by the session endpoints (needed when the
 * API runs on another origin and the cookie is not readable here). */
export function setCsrfToken(token: string | null) {
  csrfToken = token;
}

function readCsrfCookie(): string | null {
  const match = document.cookie.match(new RegExp(`(?:^|; )${CSRF_COOKIE}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

export const api = axios.create({
  baseURL: API_BASE,
  withCredentials: true, // the session lives in an HttpOnly cookie
  timeout: 30000,
});

api.interceptors.request.use((config) => {
  const method = (config.method || "get").toUpperCase();
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    const token = readCsrfCookie() || csrfToken;
    if (token) config.headers["X-CSRF-Token"] = token;
  }
  return config;
});

type UnauthorizedHandler = () => void;
let onUnauthorized: UnauthorizedHandler | null = null;
export function setUnauthorizedHandler(handler: UnauthorizedHandler | null) {
  onUnauthorized = handler;
}

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const url: string = error.config?.url || "";
    if (error.response?.status === 401 && !url.startsWith("/api/auth/")) {
      onUnauthorized?.();
    }
    return Promise.reject(error);
  },
);

export function newIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `k${Date.now()}${Math.random().toString(36).slice(2, 12)}`;
}

export function fieldErrors(error: unknown): Record<string, string> {
  const out: Record<string, string> = {};
  if (axios.isAxiosError(error) && Array.isArray(error.response?.data?.detail)) {
    for (const item of error.response!.data.detail) {
      const loc: string[] = item.loc || [];
      const field = loc[loc.length - 1];
      if (field && field !== "body") out[field] = item.msg;
    }
  }
  return out;
}

export function extractErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg;
    if (error.response?.status === 429) return "Too many requests. Wait a moment and try again.";
    if (error.code === "ECONNABORTED")
      return "The server took too long to respond. Please try again.";
    if (error.message === "Network Error")
      return "Could not reach QueueFlow. Check your connection and retry.";
  }
  return "Something went wrong. Please try again.";
}
