import { useEffect, useState } from "react";
import { WS_BASE } from "./api";
import type { QueueState } from "../types";

export function useQueueSocket(queueId: string | null) {
  const [snapshot, setSnapshot] = useState<{
    id: string;
    state: QueueState;
  } | null>(null);
  const [connection, setConnection] = useState<{
    id: string;
    status: string;
  } | null>(null);
  useEffect(() => {
    if (!queueId) return;
    const id = queueId;
    let active = true;
    let delay = 1000;
    let socket: WebSocket | null = null;
    let retry: ReturnType<typeof setTimeout> | undefined;
    let heartbeat: ReturnType<typeof setInterval> | undefined;
    let lastFrame = Date.now();
    const status = (value: string) => {
      if (active) setConnection({ id, status: value });
    };
    function connect() {
      if (!active) return;
      status(navigator.onLine ? "RECONNECTING" : "OFFLINE");
      socket = new WebSocket(`${WS_BASE}/api/queues/${id}/ws`);
      socket.onopen = () => {
        lastFrame = Date.now();
        socket?.send("ping");
      };
      socket.onmessage = (event) => {
        if (!active) return;
        lastFrame = Date.now();
        try {
          const payload = JSON.parse(event.data);
          if (payload.event === "queue_state") {
            setSnapshot({ id, state: payload.data as QueueState });
            status("LIVE");
            delay = 1000;
          }
        } catch {
          /* malformed frames never replace a valid snapshot */
        }
      };
      socket.onclose = () => {
        if (!active) return;
        status(navigator.onLine ? "RECONNECTING" : "OFFLINE");
        retry = setTimeout(connect, delay);
        delay = Math.min(delay * 2, 15000);
      };
      socket.onerror = () => socket?.close();
    }
    connect();
    heartbeat = setInterval(() => {
      if (socket?.readyState === WebSocket.OPEN) {
        if (Date.now() - lastFrame > 45000) socket.close();
        else socket.send("ping");
      }
      if (!navigator.onLine) status("OFFLINE");
    }, 15000);
    return () => {
      active = false;
      clearTimeout(retry);
      clearInterval(heartbeat);
      socket?.close();
    };
  }, [queueId]);
  const status =
    connection?.id === queueId ? connection.status : "RECONNECTING";
  return {
    state: snapshot?.id === queueId ? snapshot.state : null,
    connected: status === "LIVE",
    status,
  };
}
