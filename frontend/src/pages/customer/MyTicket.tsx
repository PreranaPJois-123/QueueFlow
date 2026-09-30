import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { AppShell } from "../../components/AppShell";
import { Button } from "../../components/Button";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { EmptyState } from "../../components/States";
import {
  Card,
  Heading,
  ResourceState,
  TicketHistory,
} from "../../components/Product";
import { activeStatus } from "../../lib/format";
import { TicketCard } from "../../components/TicketCard";
import { useResource } from "../../lib/useResource";
import { useQueueSocket } from "../../lib/useQueueSocket";
import { api, extractErrorMessage } from "../../lib/api";
import { useToast } from "../../components/Toast";
import type { CustomerData, TicketDetail } from "../../types";
export default function MyTicket() {
  const mine = useResource<CustomerData>("/api/product/mine");
  const [params, setParams] = useSearchParams();
  const selected =
    mine.data?.tickets.find((t) => t.id === params.get("ticket")) ??
    mine.data?.tickets.find((t) => activeStatus(t.status));
  const socket = useQueueSocket(selected?.queue_id ?? null);
  const detail = useResource<TicketDetail>(
    selected ? `/api/tickets/${selected.id}` : null,
    10000,
    socket.state,
  );
  const [cancel, setCancel] = useState(false);
  const { push } = useToast();
  async function cancelTicket() {
    if (!selected) return;
    try {
      await api.post(`/api/tickets/${selected.id}/cancel`);
      push("Ticket cancelled", "success");
      setCancel(false);
      detail.refresh();
      mine.refresh();
    } catch (error) {
      push(extractErrorMessage(error), "error");
    }
  }
  return (
    <AppShell variant="customer">
      <Heading
        title="My ticket"
        body="Your place in line, updated as the queue moves."
        action={
          <Link className="action-link" to="/services">
            Join a queue
          </Link>
        }
      />
      <ResourceState {...mine} />
      {!!mine.data?.tickets.filter((t) => activeStatus(t.status)).length && (
        <div className="my-5 flex flex-wrap gap-2">
          {mine.data.tickets
            .filter((t) => activeStatus(t.status))
            .map((t) => (
              <Button
                key={t.id}
                variant={selected?.id === t.id ? "primary" : "secondary"}
                onClick={() => setParams({ ticket: t.id })}
              >
                {t.token_label} · {t.queue_name}
              </Button>
            ))}
        </div>
      )}
      <ResourceState {...detail} />
      {detail.data && (
        <>
          <TicketCard detail={detail.data} connection={socket.status} />
          {detail.data.ticket.status === "WAITING" && (
            <Button
              className="mt-4"
              variant="secondary"
              onClick={() => setCancel(true)}
            >
              Cancel ticket
            </Button>
          )}
        </>
      )}
      {mine.data && !selected && (
        <div className="mt-6">
          <EmptyState
            title="No active ticket"
            body="Browse services to reserve your place in an open queue."
            action={
              <Link to="/services" className="action-link">
                Browse services
              </Link>
            }
          />
        </div>
      )}
      {mine.data && (
        <Card title="Ticket history" className="mt-8">
          <TicketHistory tickets={mine.data.tickets} />
        </Card>
      )}
      <ConfirmDialog
        open={cancel}
        title="Cancel this ticket?"
        body="You will lose your place in the queue."
        confirmLabel="Cancel ticket"
        danger
        onConfirm={cancelTicket}
        onCancel={() => setCancel(false)}
      />
    </AppShell>
  );
}
