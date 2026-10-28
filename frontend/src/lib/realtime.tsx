import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { api, wsUrl } from "./api";
import { useAuth } from "./auth";
import { useToast } from "../components/Toast";
import type { AppNotification } from "../types";

export interface BookingUpdate {
  reference: string;
  status: string;
  position: number | null;
  eta_minutes: number | null;
  current_token: string | null;
  delay_minutes: number;
  queue_status: string;
}

interface RealtimeValue {
  connected: boolean;
  notifications: AppNotification[];
  unread: number;
  refresh: () => Promise<void>;
  markRead: (id: string) => Promise<void>;
  markAllRead: () => Promise<void>;
  subscribeBookings: (listener: (update: BookingUpdate) => void) => () => void;
}

const RealtimeContext = createContext<RealtimeValue | null>(null);
// Only time-sensitive alerts interrupt with a toast/sound; confirmations of the
// user's own actions already show on the page and just land in the bell.
const ALERT_TYPES = new Set(["TURN_APPROACHING", "CALLED", "SERVICE_DELAY"]);

let audio: AudioContext | null = null;
/** Short two-tone chime. Browsers may block audio until the user has interacted
 * with the page; failures are ignored because a visible toast is always shown. */
// oxlint-disable-next-line react/only-export-components -- used by the profile "test sound" button.
export async function playChime(): Promise<boolean> {
  try {
    audio = audio || new AudioContext();
    if (audio.state === "suspended") await audio.resume();
    const now = audio.currentTime;
    [660, 880].forEach((freq, i) => {
      const osc = audio!.createOscillator();
      const gain = audio!.createGain();
      osc.frequency.value = freq;
      gain.gain.setValueAtTime(0.0001, now + i * 0.18);
      gain.gain.exponentialRampToValueAtTime(0.2, now + i * 0.18 + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, now + i * 0.18 + 0.3);
      osc.connect(gain).connect(audio!.destination);
      osc.start(now + i * 0.18);
      osc.stop(now + i * 0.18 + 0.32);
    });
    return true;
  } catch {
    return false;
  }
}

export function RealtimeProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const { push } = useToast();
  const [connected, setConnected] = useState(false);
  const [notifications, setNotifications] = useState<AppNotification[]>([]);
  const [unread, setUnread] = useState(0);
  const listeners = useRef(new Set<(update: BookingUpdate) => void>());
  const prefs = useRef(user);
  useEffect(() => {
    prefs.current = user;
  }, [user]);

  const refresh = useCallback(async () => {
    try {
      const { data } = await api.get<{ items: AppNotification[]; unread: number }>("/api/notifications?limit=30");
      setNotifications(data.items);
      setUnread(data.unread);
    } catch {
      /* keep the last known list; the poll or socket will retry */
    }
  }, []);

  const announce = useCallback(
    (n: AppNotification) => {
      if (!ALERT_TYPES.has(n.type)) return;
      push(n.message, "info");
      const current = prefs.current;
      if (!current) return;
      if (current.pref_sound_enabled) void playChime();
      if (current.pref_browser_enabled && "Notification" in window && Notification.permission === "granted"
          && document.visibilityState !== "visible") {
        try {
          new Notification("QueueFlow", { body: n.message, tag: n.id });
        } catch {
          /* some browsers only allow notifications from a service worker */
        }
      }
    },
    [push],
  );

  useEffect(() => {
    if (!user) {
      setNotifications([]);
      setUnread(0);
      return;
    }
    let socket: WebSocket | null = null;
    let closed = false;
    let attempt = 0;
    let reconnect: ReturnType<typeof setTimeout> | undefined;
    let ping: ReturnType<typeof setInterval> | undefined;
    void refresh();

    const connect = () => {
      socket = new WebSocket(wsUrl("/api/ws"));
      socket.onopen = () => {
        attempt = 0;
        setConnected(true);
        void refresh(); // catch up on anything missed while disconnected
        ping = setInterval(() => socket?.readyState === WebSocket.OPEN && socket.send("ping"), 25000);
      };
      socket.onmessage = (event) => {
        let message: { type: string; data?: unknown };
        try {
          message = JSON.parse(event.data);
        } catch {
          return;
        }
        if (message.type === "notification") {
          const n = message.data as AppNotification;
          setNotifications((prev) => (prev.some((p) => p.id === n.id) ? prev : [n, ...prev].slice(0, 50)));
          setUnread((u) => u + 1);
          announce(n);
        } else if (message.type === "booking_update") {
          listeners.current.forEach((listener) => listener(message.data as BookingUpdate));
        }
      };
      socket.onclose = (event) => {
        setConnected(false);
        clearInterval(ping);
        if (closed || event.code === 4401) return; // signed out: do not retry
        const delay = Math.min(30000, 1000 * 2 ** attempt++) + Math.random() * 500;
        reconnect = setTimeout(connect, delay);
      };
    };
    connect();
    // Polling fallback while the socket is down.
    const poll = setInterval(() => {
      if (socket?.readyState !== WebSocket.OPEN) void refresh();
    }, 30000);
    return () => {
      closed = true;
      clearTimeout(reconnect);
      clearInterval(ping);
      clearInterval(poll);
      socket?.close();
    };
  }, [user?.id, refresh, announce]); // eslint-disable-line react-hooks/exhaustive-deps

  const markRead = useCallback(async (id: string) => {
    await api.post(`/api/notifications/${id}/read`);
    setNotifications((prev) => prev.map((n) => (n.id === id ? { ...n, is_read: true } : n)));
    setUnread((u) => Math.max(0, u - 1));
  }, []);

  const markAllRead = useCallback(async () => {
    await api.post("/api/notifications/read-all");
    setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
    setUnread(0);
  }, []);

  const subscribeBookings = useCallback((listener: (update: BookingUpdate) => void) => {
    listeners.current.add(listener);
    return () => {
      listeners.current.delete(listener);
    };
  }, []);

  return (
    <RealtimeContext.Provider value={{ connected, notifications, unread, refresh, markRead, markAllRead,
                                       subscribeBookings }}>
      {children}
    </RealtimeContext.Provider>
  );
}

// oxlint-disable-next-line react/only-export-components -- Context provider and hook share one public API.
export function useRealtime() {
  const ctx = useContext(RealtimeContext);
  if (!ctx) throw new Error("useRealtime must be used within RealtimeProvider");
  return ctx;
}
