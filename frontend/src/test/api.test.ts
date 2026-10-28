import { afterEach, describe, expect, it } from "vitest";
import { api, setCsrfToken } from "../lib/api";
import type { InternalAxiosRequestConfig } from "axios";

async function run(config: Partial<InternalAxiosRequestConfig>) {
  // Execute the request interceptors only (no network).
  const handlers = (api.interceptors.request as unknown as { handlers: { fulfilled: (c: unknown) => unknown }[] }).handlers;
  let current: InternalAxiosRequestConfig = { headers: {} as InternalAxiosRequestConfig["headers"], ...config } as InternalAxiosRequestConfig;
  for (const h of handlers) current = (await h.fulfilled(current)) as InternalAxiosRequestConfig;
  return current;
}

describe("api client", () => {
  afterEach(() => { document.cookie = "qf_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT"; setCsrfToken(null); });

  it("sends cookies, never a bearer token", () => {
    expect(api.defaults.withCredentials).toBe(true);
  });
  it("adds the CSRF header from the cookie on unsafe requests only", async () => {
    document.cookie = "qf_csrf=cookie-token";
    expect((await run({ method: "post" })).headers["X-CSRF-Token"]).toBe("cookie-token");
    expect((await run({ method: "get" })).headers["X-CSRF-Token"]).toBeUndefined();
  });
  it("falls back to the token returned by the session endpoint", async () => {
    setCsrfToken("memory-token");
    expect((await run({ method: "delete" })).headers["X-CSRF-Token"]).toBe("memory-token");
  });
});
