import { useCallback, useEffect, useState } from "react";
import { api, extractErrorMessage } from "./api";

/** Abort obsolete requests; retain and label stale data when refresh fails. */
export function useResource<T>(
  url: string | null,
  interval = 15000,
  revision: unknown = null,
) {
  const [snapshot, setSnapshot] = useState<{
    url: string;
    data: T;
    at: Date;
  } | null>(null);
  const [failure, setFailure] = useState<{
    url: string;
    message: string;
  } | null>(null);
  const [version, setVersion] = useState(0);
  const refresh = useCallback(() => setVersion((v) => v + 1), []);
  useEffect(() => {
    if (!url) return;
    const controller = new AbortController();
    let running = false;
    async function load() {
      if (running || controller.signal.aborted) return;
      running = true;
      try {
        const { data } = await api.get<T>(url!, { signal: controller.signal });
        if (!controller.signal.aborted) {
          setSnapshot({ url: url!, data, at: new Date() });
          setFailure(null);
        }
      } catch (error) {
        if (!controller.signal.aborted)
          setFailure({ url: url!, message: extractErrorMessage(error) });
      } finally {
        running = false;
      }
    }
    void load();
    const timer = interval
      ? setInterval(() => {
          void load();
        }, interval)
      : null;
    const visible = () => {
      if (document.visibilityState === "visible") void load();
    };
    document.addEventListener("visibilitychange", visible);
    return () => {
      controller.abort();
      if (timer) clearInterval(timer);
      document.removeEventListener("visibilitychange", visible);
    };
  }, [url, interval, version, revision]);
  const data = snapshot?.url === url ? snapshot.data : null;
  const error = failure?.url === url ? failure.message : null;
  return {
    data,
    error,
    loading: !!url && !data && !error,
    refresh,
    updatedAt: snapshot?.url === url ? snapshot.at : null,
  };
}
