import { useState } from "react";
import { Link } from "react-router-dom";
import { AppShell } from "../../components/AppShell";
import { Button } from "../../components/Button";
import { QueueStatusBadge } from "../../components/Badge";
import { Heading, Card, ResourceState } from "../../components/Product";
import { predictionLabel } from "../../lib/format";
import { EmptyState } from "../../components/States";
import { useResource } from "../../lib/useResource";
import { useToast } from "../../components/Toast";
import { api, extractErrorMessage } from "../../lib/api";
import type { QueueSummary, Service } from "../../types";
export default function Queues() {
  const queues = useResource<QueueSummary[]>("/api/product/queues", 5000);
  const services = useResource<Service[]>("/api/services");
  const [show, setShow] = useState(false);
  const [name, setName] = useState("");
  const [service, setService] = useState("");
  const [pending, setPending] = useState(false);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("ALL");
  const { push } = useToast();
  async function create(e: React.FormEvent) {
    e.preventDefault();
    setPending(true);
    try {
      await api.post("/api/queues", {
        name: name.trim(),
        service_id: service || services.data?.[0]?.id,
      });
      push("Queue opened", "success");
      setShow(false);
      setName("");
      queues.refresh();
    } catch (e) {
      push(extractErrorMessage(e), "error");
    } finally {
      setPending(false);
    }
  }
  const filtered = queues.data?.filter(
    (q) =>
      `${q.name} ${q.service_name}`
        .toLowerCase()
        .includes(search.toLowerCase()) &&
      (status === "ALL" || q.status === status),
  );
  return (
    <AppShell variant="staff">
      <Heading
        title="Queues"
        body="Operate every service desk from one workspace."
        action={
          <Button
            onClick={() => setShow(!show)}
            disabled={!services.data?.length}
          >
            {show ? "Close form" : "Open new queue"}
          </Button>
        }
      />
      <ResourceState {...queues} />
      <ResourceState {...services} />
      {services.data?.length === 0 && (
        <p className="my-5 text-sm text-ink-500">
          Create a service in{" "}
          <Link className="text-signal-700" to="/staff/settings">
            Settings
          </Link>{" "}
          to open a queue.
        </p>
      )}
      {show && (
        <Card title="Open queue" className="my-6 max-w-lg">
          <form onSubmit={create} className="space-y-4">
            <label className="label">
              Service
              <select
                className="field mt-2"
                value={service || services.data?.[0]?.id || ""}
                onChange={(e) => setService(e.target.value)}
              >
                {services.data?.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="label">
              Queue name
              <input
                className="field mt-2"
                required
                maxLength={255}
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Main service desk"
              />
            </label>
            <Button loading={pending} disabled={!name.trim()} type="submit">
              Open queue
            </Button>
          </form>
        </Card>
      )}
      <div className="my-6 flex flex-wrap gap-3">
        <input
          aria-label="Search queues"
          className="field max-w-sm"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search queues or services…"
        />
        <select
          aria-label="Queue status filter"
          className="field max-w-xs"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
        >
          {["ALL", "OPEN", "PAUSED", "CLOSED"].map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>
      {filtered && !filtered.length && (
        <EmptyState
          title="No matching queues"
          body="Open a new queue or change your filters."
        />
      )}
      <div className="grid gap-5 lg:grid-cols-2">
        {filtered?.map((q) => (
          <Card key={q.id}>
            <div className="flex justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold">{q.name}</h2>
                <p className="mt-1 text-sm text-ink-500">{q.service_name}</p>
              </div>
              <QueueStatusBadge status={q.status} />
            </div>
            <dl className="my-5 grid grid-cols-3 gap-3">
              {[
                ["Waiting", q.waiting_count],
                ["Now serving", q.current_serving_label ?? "—"],
                ["Est. wait", `${q.estimated_wait_minutes}m`],
              ].map(([label, value]) => (
                <div key={label}>
                  <dt className="text-xs text-ink-500">{label}</dt>
                  <dd className="mt-2 text-xl font-semibold">{value}</dd>
                </div>
              ))}
            </dl>
            <p className="mb-4 text-xs text-ink-500">
              {predictionLabel(q.prediction_source)}
            </p>
            <Link className="action-link" to={`/staff/queue/${q.id}`}>
              Open controls →
            </Link>
          </Card>
        ))}
      </div>
      <p className="mt-5 text-xs text-ink-500">
        Queue snapshots refresh every 5 seconds. Individual controls receive
        WebSocket updates.
      </p>
    </AppShell>
  );
}
