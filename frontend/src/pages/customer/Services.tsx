import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { AppShell } from "../../components/AppShell";
import { Button } from "../../components/Button";
import { QueueStatusBadge } from "../../components/Badge";
import { EmptyState } from "../../components/States";
import { Card, Heading, ResourceState } from "../../components/Product";
import { predictionLabel, activeStatus } from "../../lib/format";
import { useResource } from "../../lib/useResource";
import { api, extractErrorMessage } from "../../lib/api";
import { useToast } from "../../components/Toast";
import type {
  QueueSummary,
  Service,
  TicketDetail,
  CustomerData,
} from "../../types";
export default function Services() {
  const services = useResource<Service[]>("/api/services");
  const queues = useResource<QueueSummary[]>("/api/product/queues", 10000);
  const mine = useResource<CustomerData>("/api/product/mine");
  const [search, setSearch] = useState("");
  const [pending, setPending] = useState<string | null>(null);
  const navigate = useNavigate();
  const { push } = useToast();
  async function join(id: string) {
    setPending(id);
    try {
      const { data } = await api.post<TicketDetail>(`/api/queues/${id}/join`);
      push(
        `Ticket ${data.ticket.token_label} · position ${data.people_ahead + 1} · ~${data.estimated_wait_minutes} min`,
        "success",
      );
      navigate(`/my-ticket?ticket=${data.ticket.id}`);
    } catch (e) {
      push(extractErrorMessage(e), "error");
      mine.refresh();
      queues.refresh();
    } finally {
      setPending(null);
    }
  }
  const filtered = services.data?.filter((s) =>
    `${s.name} ${s.description ?? ""}`
      .toLowerCase()
      .includes(search.toLowerCase()),
  );
  return (
    <AppShell variant="customer">
      <Heading
        title="Find your service"
        body="Join an open queue now, or reserve an appointment for later."
      />
      <input
        aria-label="Search services"
        className="field my-6 max-w-md"
        placeholder="Search services…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />
      <ResourceState {...services} />
      <ResourceState {...queues} />
      <ResourceState {...mine} />
      {filtered && !filtered.length && (
        <EmptyState
          title="No services found"
          body="Try another search, or check back when a service is published."
        />
      )}
      <div className="grid gap-6 xl:grid-cols-2">
        {filtered?.map((s) => (
          <Card key={s.id}>
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-widest text-signal-700">
                  Service
                </p>
                <h2 className="mt-2 text-xl font-semibold">{s.name}</h2>
                <p className="mt-2 text-sm text-ink-500">
                  {s.description ||
                    "Contact the service desk for visit details."}
                </p>
              </div>
              <span className="rounded-full bg-signal-50 px-3 py-1 text-xs text-signal-700">
                Available
              </span>
            </div>
            <div className="mt-5 space-y-3">
              {queues.data
                ?.filter((q) => q.service_id === s.id)
                .map((q) => {
                  const ticket = mine.data?.tickets.find(
                    (t) => t.queue_id === q.id && activeStatus(t.status),
                  );
                  return (
                    <div
                      key={q.id}
                      className="rounded-xl border border-ink-100 p-4"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <h3 className="text-sm font-semibold">{q.name}</h3>
                        <QueueStatusBadge status={q.status} />
                      </div>
                      <div className="my-4 grid grid-cols-3 gap-3 text-xs text-ink-500">
                        <p>
                          Waiting
                          <strong className="mt-1 block text-lg text-ink-900">
                            {q.waiting_count}
                          </strong>
                        </p>
                        <p>
                          Est. wait
                          <strong className="mt-1 block text-lg text-ink-900">
                            {q.estimated_wait_minutes}m
                          </strong>
                        </p>
                        <p>
                          Service duration
                          <strong className="mt-1 block text-lg text-ink-900">
                            ~{q.estimated_service_minutes}m
                          </strong>
                        </p>
                      </div>
                      <p className="mb-3 text-xs text-ink-500">
                        {predictionLabel(q.prediction_source)}
                      </p>
                      {ticket ? (
                        <Link
                          to={`/my-ticket?ticket=${ticket.id}`}
                          className="text-sm font-semibold text-signal-700"
                        >
                          View {ticket.token_label} →
                        </Link>
                      ) : (
                        <Button
                          size="sm"
                          disabled={
                            !mine.data ||
                            q.status !== "OPEN" ||
                            pending !== null
                          }
                          loading={pending === q.id}
                          onClick={() => join(q.id)}
                        >
                          Join queue
                        </Button>
                      )}
                    </div>
                  );
                })}
              {queues.data &&
                !queues.data.some((q) => q.service_id === s.id) && (
                  <p className="rounded-lg bg-ink-50 p-4 text-sm text-ink-500">
                    No live queue is available. You can book an appointment.
                  </p>
                )}
            </div>
            <Link
              to={`/appointments?service=${s.id}`}
              className="mt-5 inline-block text-sm font-semibold text-signal-700"
            >
              Book an appointment →
            </Link>
          </Card>
        ))}
      </div>
    </AppShell>
  );
}
