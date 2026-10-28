import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { dateTime } from "../lib/format";
import { useRealtime } from "../lib/realtime";

export function NotificationBell() {
  const { notifications, unread, markRead, markAllRead, connected } = useRealtime();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && setOpen(false);
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", esc);
    };
  }, [open]);

  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setOpen((o) => !o)} aria-expanded={open} aria-haspopup="true"
        aria-label={unread ? `Notifications, ${unread} unread` : "Notifications"}
        className="relative flex items-center gap-2 rounded-lg border border-ink-200 bg-white px-3 py-1.5 text-sm font-medium text-ink-700 hover:bg-ink-50">
        <svg aria-hidden viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M6 8a6 6 0 1 1 12 0c0 7 3 9 3 9H3s3-2 3-9" /><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
        </svg>
        <span className="hidden sm:inline">Notifications</span>
        {unread > 0 && (
          <span className="font-display min-w-5 rounded-full bg-rose-500 px-1.5 text-xs font-semibold text-white">{unread}</span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 z-40 mt-2 w-[min(22rem,calc(100vw-2rem))] overflow-hidden rounded-xl border border-ink-100 bg-white shadow-xl">
          <div className="flex items-center justify-between border-b border-ink-100 px-4 py-3">
            <p className="text-sm font-semibold text-ink-900">Notifications</p>
            <span className={`text-xs ${connected ? "text-signal-600" : "text-ink-400"}`}>
              {connected ? "Live" : "Reconnecting, checking every 30 s"}
            </span>
          </div>
          <ul className="max-h-80 divide-y divide-ink-100 overflow-y-auto">
            {notifications.length === 0 && (
              <li className="px-4 py-8 text-center text-sm text-ink-400">Booking updates and turn alerts appear here.</li>
            )}
            {notifications.slice(0, 8).map((n) => (
              <li key={n.id} className={n.is_read ? "" : "bg-signal-50/50"}>
                <button className="w-full px-4 py-3 text-left" onClick={() => !n.is_read && void markRead(n.id)}>
                  <p className="text-sm text-ink-800">{n.message}</p>
                  <p className="mt-1 text-xs text-ink-400">{dateTime(n.created_at)}{!n.is_read && ", unread"}</p>
                </button>
              </li>
            ))}
          </ul>
          <div className="flex justify-between border-t border-ink-100 px-4 py-2.5 text-sm">
            <button onClick={() => void markAllRead()} disabled={!unread} className="font-medium text-ink-600 disabled:text-ink-300">Mark all read</button>
            <Link to="/notifications" onClick={() => setOpen(false)} className="font-medium text-signal-700">See all</Link>
          </div>
        </div>
      )}
    </div>
  );
}
