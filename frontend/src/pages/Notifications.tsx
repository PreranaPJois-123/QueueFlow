import { useEffect } from "react";
import { Link } from "react-router-dom";
import { AppShell } from "../components/AppShell";
import { Button } from "../components/Button";
import { EmptyState } from "../components/States";
import { PageHeader } from "../components/ui";
import { dateTime } from "../lib/format";
import { useRealtime } from "../lib/realtime";

const LABELS: Record<string, string> = {
  TURN_APPROACHING: "Turn approaching", CALLED: "Your turn", SERVICE_DELAY: "Delay", BOOKING_CONFIRMED: "Confirmed",
  BOOKING_UPDATED: "Updated", BOOKING_CANCELLED: "Cancelled", QUEUE_UPDATE: "Queue", SYSTEM: "System",
};

export default function Notifications() {
  const { notifications, unread, markRead, markAllRead, refresh, connected } = useRealtime();
  useEffect(() => { void refresh(); }, [refresh]);

  return (
    <AppShell>
      <PageHeader title="Notifications" description={connected ? "Updates arrive live." : "Live connection unavailable; this list refreshes every 30 seconds."}
        actions={<>
          <Link to="/profile#notifications" className="action-link">Sound and browser alerts</Link>
          <Button variant="secondary" disabled={!unread} onClick={() => void markAllRead()}>Mark all read</Button>
        </>} />
      {notifications.length === 0 ? (
        <EmptyState title="No notifications yet" body="Confirmations, turn alerts and delays for your bookings will appear here." />
      ) : (
        <ul className="divide-y divide-ink-100 overflow-hidden rounded-2xl border border-ink-100 bg-white">
          {notifications.map((n) => (
            <li key={n.id} className={`flex flex-col gap-2 px-5 py-4 sm:flex-row sm:items-start sm:gap-6 ${n.is_read ? "" : "bg-signal-50/40"}`}>
              <span className={`w-36 shrink-0 text-xs font-semibold ${n.type === "TURN_APPROACHING" || n.type === "CALLED" ? "text-amber-600" : n.type === "BOOKING_CANCELLED" ? "text-rose-600" : "text-ink-500"}`}>
                {LABELS[n.type] || n.type}
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-sm text-ink-800">{n.message}</p>
                <p className="mt-1 text-xs text-ink-400">{dateTime(n.created_at)}</p>
              </div>
              {!n.is_read && <Button size="sm" variant="ghost" onClick={() => void markRead(n.id)}>Mark read</Button>}
            </li>
          ))}
        </ul>
      )}
    </AppShell>
  );
}
