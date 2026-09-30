import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AppShell } from "../../components/AppShell";
import { Button } from "../../components/Button";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { TicketStatusBadge, QueueStatusBadge } from "../../components/Badge";
import {
  Heading,
  Card,
  ResourceState,
  Connection,
  Metric,
} from "../../components/Product";
import { dateTime } from "../../lib/format";
import { EmptyState } from "../../components/States";
import { useResource } from "../../lib/useResource";
import { useQueueSocket } from "../../lib/useQueueSocket";
import { api, extractErrorMessage } from "../../lib/api";
import { useToast } from "../../components/Toast";
import type { QueueSummary, OperatingTicket } from "../../types";
export default function QueueDetail() {
  const { id } = useParams();
  const socket = useQueueSocket(id ?? null);
  const summaries = useResource<QueueSummary[]>(
    "/api/product/queues",
    10000,
    socket.state,
  );
  const tickets = useResource<OperatingTicket[]>(
    id ? `/api/product/queues/${id}/tickets` : null,
    10000,
    socket.state,
  );
  const queue = summaries.data?.find((q) => q.id === id);
  const current = tickets.data?.find((t) =>
    ["CALLED", "SERVING"].includes(t.status),
  );
  const waiting = tickets.data?.filter((t) => t.status === "WAITING") ?? [];
  const [pending, setPending] = useState(false);
  const [confirm, setConfirm] = useState<{
    path: string;
    title: string;
    body: string;
  } | null>(null);
  const { push } = useToast();
  async function act(path: string) {
    setPending(true);
    try {
      await api.post(path);
      push("Queue updated", "success");
      setConfirm(null);
      summaries.refresh();
      tickets.refresh();
    } catch (e) {
      push(extractErrorMessage(e), "error");
      summaries.refresh();
      tickets.refresh();
    } finally {
      setPending(false);
    }
  }
  const base = `/api/staff/queues/${id}`;
  return (
    <AppShell variant="staff">
      <Link
        to="/staff/queues"
        className="mb-4 inline-block text-sm text-signal-700"
      >
        ← All queues
      </Link>
      <Heading
        title={queue?.name ?? "Queue control"}
        body={queue?.service_name}
        action={<Connection status={socket.status} />}
      />
      <ResourceState {...summaries} />
      <ResourceState {...tickets} />
      {summaries.data && !queue && (
        <EmptyState
          title="Queue not found"
          body="Return to the queues list to choose another desk."
        />
      )}
      {queue && (
        <>
          <div className="my-6 flex flex-wrap items-center gap-3">
            <QueueStatusBadge status={queue.status} />
            {queue.status === "OPEN" && (
              <Button
                disabled={pending}
                variant="secondary"
                onClick={() =>
                  setConfirm({
                    path: `${base}/pause`,
                    title: "Pause queue?",
                    body: "New customers cannot join until the queue resumes.",
                  })
                }
              >
                Pause
              </Button>
            )}
            {queue.status === "PAUSED" && (
              <Button
                disabled={pending}
                variant="secondary"
                onClick={() => act(`${base}/resume`)}
              >
                Resume
              </Button>
            )}
            {queue.status !== "CLOSED" && (
              <Button
                disabled={pending}
                variant="danger"
                onClick={() =>
                  setConfirm({
                    path: `${base}/close`,
                    title: "Close queue?",
                    body: "Closing is permanent for this queue. All active tickets must be finished or skipped first.",
                  })
                }
              >
                Close queue
              </Button>
            )}
          </div>
          <div className="mb-6 grid gap-4 sm:grid-cols-3">
            <Metric label="Waiting" value={queue.waiting_count} />
            <Metric
              label="Estimated wait for new arrival"
              value={`~${queue.estimated_wait_minutes}m`}
            />
            <Metric
              label="Estimated service duration"
              value={`~${queue.estimated_service_minutes}m`}
            />
          </div>
          <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
            <Card title="Current visit">
              <p className="token-display text-6xl font-bold">
                {queue.current_serving_label ?? "—"}
              </p>
              {current && (
                <div className="mt-4">
                  <p className="font-semibold">{current.customer_name}</p>
                  <p className="mt-1 break-all text-sm text-ink-500">
                    {current.customer_email}
                  </p>
                  <div className="mt-3">
                    <TicketStatusBadge status={current.status} />
                  </div>
                </div>
              )}
              <div className="mt-6 flex flex-wrap gap-3">
                <Button
                  loading={pending}
                  disabled={
                    queue.status !== "OPEN" ||
                    !!queue.now_serving_ticket_id ||
                    !waiting.length ||
                    !tickets.data ||
                    !!tickets.error
                  }
                  onClick={() => act(`${base}/next`)}
                >
                  Call next
                </Button>
                {current?.status === "CALLED" && (
                  <Button
                    disabled={pending || !!tickets.error}
                    onClick={() =>
                      act(`/api/staff/tickets/${current.id}/start`)
                    }
                  >
                    Start service
                  </Button>
                )}
                {current?.status === "SERVING" && (
                  <Button
                    disabled={pending || !!tickets.error}
                    onClick={() =>
                      act(`/api/staff/tickets/${current.id}/serve`)
                    }
                  >
                    Complete visit
                  </Button>
                )}
                {current && (
                  <Button
                    disabled={pending || !!tickets.error}
                    variant="danger"
                    onClick={() =>
                      setConfirm({
                        path: `/api/staff/tickets/${current.id}/skip`,
                        title: `Skip ${current.token_label}?`,
                        body: "The customer will lose this place in the queue.",
                      })
                    }
                  >
                    Skip
                  </Button>
                )}
              </div>
              <p className="mt-5 text-xs text-ink-500">
                Call → start service → complete. Finish the current visit before
                calling another customer.
              </p>
            </Card>
            <Card title={`Waiting tickets (${waiting.length})`}>
              {!waiting.length && <EmptyState title="No one waiting" />}
              {waiting.map((t, i) => (
                <div
                  key={t.id}
                  className="mb-3 rounded-xl border border-ink-100 p-4"
                >
                  <div className="flex justify-between gap-2">
                    <strong>{t.token_label}</strong>
                    <span className="text-xs text-ink-500">
                      Position {i + 1 + (current ? 1 : 0)}
                    </span>
                  </div>
                  <p className="mt-2 text-sm">{t.customer_name}</p>
                  <p className="mt-1 text-xs text-ink-500">
                    Waiting {t.waiting_minutes} min · joined{" "}
                    {dateTime(t.created_at)}
                  </p>
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={pending}
                    className="mt-2"
                    onClick={() =>
                      setConfirm({
                        path: `/api/staff/tickets/${t.id}/skip`,
                        title: `Skip ${t.token_label}?`,
                        body: "This removes the customer from the waiting list.",
                      })
                    }
                  >
                    Skip ticket
                  </Button>
                </div>
              ))}
            </Card>
          </div>
        </>
      )}
      <ConfirmDialog
        open={!!confirm}
        title={confirm?.title ?? ""}
        body={confirm?.body ?? ""}
        danger
        onConfirm={() => (confirm ? act(confirm.path) : undefined)}
        onCancel={() => setConfirm(null)}
      />
    </AppShell>
  );
}
