import { useClock } from "../../lib/useClock";
import { Link } from "react-router-dom";
import { AppShell } from "../../components/AppShell";
import {
  Card,
  Heading,
  Metric,
  ResourceState,
  TicketHistory,
} from "../../components/Product";
import { activeStatus, dateTime } from "../../lib/format";
import { EmptyState } from "../../components/States";
import { TicketCard } from "../../components/TicketCard";
import { Button } from "../../components/Button";
import { useResource } from "../../lib/useResource";
import { useQueueSocket } from "../../lib/useQueueSocket";
import { useAuth } from "../../lib/auth";
import { api, extractErrorMessage } from "../../lib/api";
import { useToast } from "../../components/Toast";
import type { CustomerData, TicketDetail } from "../../types";
export default function Dashboard() {
  const now = useClock();
  const { user } = useAuth();
  const mine = useResource<CustomerData>("/api/product/mine");
  const ticket = mine.data?.tickets.find((t) => activeStatus(t.status));
  const socket = useQueueSocket(ticket?.queue_id ?? null);
  const detail = useResource<TicketDetail>(
    ticket ? `/api/tickets/${ticket.id}` : null,
    10000,
    socket.state,
  );
  const upcoming =
    mine.data?.appointments.filter(
      (a) =>
        ["SCHEDULED", "CHECKED_IN"].includes(a.status) &&
        new Date(a.scheduled_time).getTime() >= now,
    ) ?? [];
  const { push } = useToast();
  async function read(id: string) {
    try {
      await api.post(`/api/product/notifications/${id}/read`);
      mine.refresh();
    } catch (e) {
      push(extractErrorMessage(e), "error");
    }
  }
  return (
    <AppShell variant="customer">
      <Heading
        title={`Welcome back, ${user?.full_name.split(" ")[0] ?? ""}`}
        body="Less time waiting. More time for everything else."
      />
      <div className="my-6 flex flex-wrap gap-3">
        {[
          ["/join-queue", "Join queue"],
          ["/appointments", "Book appointment"],
          ["/my-ticket", "View ticket"],
          ["/services", "View services"],
        ].map(([url, label]) => (
          <Link key={url} className="action-link" to={url}>
            {label} →
          </Link>
        ))}
      </div>
      <ResourceState {...mine} />
      {mine.data && (
        <>
          <div className="mb-6 grid gap-4 sm:grid-cols-3">
            <Metric
              label="Active tickets"
              value={
                mine.data.tickets.filter((t) => activeStatus(t.status)).length
              }
            />
            <Metric
              label="Completed visits"
              value={
                mine.data.tickets.filter((t) => t.status === "SERVED").length
              }
            />
            <Metric label="Upcoming appointments" value={upcoming.length} />
          </div>
          <div className="grid gap-6 lg:grid-cols-3">
            <div className="lg:col-span-2">
              <ResourceState {...detail} />
              {detail.data ? (
                <TicketCard detail={detail.data} connection={socket.status} />
              ) : (
                !ticket && (
                  <EmptyState
                    title="Your next visit starts here"
                    body="Choose a service and join a live queue."
                    action={
                      <Link className="action-link" to="/services">
                        Find a service →
                      </Link>
                    }
                  />
                )
              )}
            </div>
            <Card title="Upcoming appointments">
              {upcoming.length ? (
                upcoming.slice(0, 3).map((a) => (
                  <div key={a.id} className="mb-4 border-b border-ink-100 pb-4">
                    <p className="text-sm font-semibold">{a.service_name}</p>
                    <p className="mt-2 text-xs text-ink-500">
                      {dateTime(a.scheduled_time)}
                    </p>
                    <p className="mt-2 text-xs text-signal-700">
                      {a.status.replaceAll("_", " ")}
                    </p>
                  </div>
                ))
              ) : (
                <p className="text-sm text-ink-500">
                  No upcoming appointments. Plan your next visit when it suits
                  you.
                </p>
              )}
              <Link
                to="/appointments"
                className="mt-4 inline-block text-sm font-semibold text-signal-700"
              >
                Manage appointments →
              </Link>
            </Card>
          </div>
          <Card title="Notifications" className="mt-6">
            {mine.data.notifications.length ? (
              mine.data.notifications.slice(0, 5).map((n) => (
                <div
                  key={n.id}
                  className="flex items-start justify-between gap-3 border-b border-ink-50 py-3"
                >
                  <div>
                    <p
                      className={`text-sm ${n.is_read ? "text-ink-500" : "font-semibold"}`}
                    >
                      {n.message}
                    </p>
                    <p className="mt-1 text-xs text-ink-500">
                      {dateTime(n.created_at)}
                    </p>
                  </div>
                  {!n.is_read && (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => read(n.id)}
                    >
                      Mark read
                    </Button>
                  )}
                </div>
              ))
            ) : (
              <p className="text-sm text-ink-500">
                Updates from your service desk will appear here.
              </p>
            )}
          </Card>
          <Card title="Recent activity" className="mt-6">
            <TicketHistory tickets={mine.data.tickets.slice(0, 5)} />
          </Card>
        </>
      )}
    </AppShell>
  );
}
