import { Link } from "react-router-dom";
import { AppShell } from "../../components/AppShell";
import {
  Heading,
  Card,
  Metric,
  ResourceState,
  TrendChart,
} from "../../components/Product";

import { QueueStatusBadge } from "../../components/Badge";
import { EmptyState } from "../../components/States";
import { useResource } from "../../lib/useResource";
import type { QueueSummary, Analytics, Trends } from "../../types";
export default function Dashboard() {
  const queues = useResource<QueueSummary[]>("/api/product/queues", 5000);
  const analytics = useResource<Analytics>("/api/analytics");
  const trends = useResource<Trends>("/api/product/trends");
  return (
    <AppShell variant="staff">
      <Heading
        title="Operations overview"
        body="A live view of your service desks, customers, and visits."
        action={
          <Link className="action-link" to="/staff/queues">
            Manage queues →
          </Link>
        }
      />
      <ResourceState {...queues} />
      <ResourceState {...analytics} />
      <ResourceState {...trends} />
      {analytics.data && trends.data && (
        <div className="my-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {[
            ["Open queues", analytics.data.active_queues],
            ["Waiting customers", trends.data.waiting],
            ["Called / serving", trends.data.serving],
            ["Completed today", analytics.data.completed_tickets_today],
            ["Skipped today", analytics.data.skipped_tickets_today],
            ["Average wait", `${analytics.data.average_wait_minutes}m`],
            ["Average service", `${analytics.data.average_service_minutes}m`],
            ["Active appointments", trends.data.active_appointments],
          ].map(([label, value]) => (
            <Metric key={label} label={String(label)} value={value} />
          ))}
        </div>
      )}
      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card title="Queue activity">
          <p className="mb-4 text-xs text-ink-500">
            Refreshes every 5 seconds
            {queues.updatedAt
              ? ` · updated ${queues.updatedAt.toLocaleTimeString()}`
              : ""}
          </p>
          {queues.data?.length === 0 && (
            <EmptyState
              title="No service desks yet"
              body="Create a service in Settings, then open a queue."
            />
          )}
          {queues.data
            ?.filter((q) => q.status !== "CLOSED")
            .map((q) => (
              <Link
                key={q.id}
                to={`/staff/queue/${q.id}`}
                className="mb-3 block rounded-xl border border-ink-100 p-4 hover:border-signal-400"
              >
                <div className="flex items-center justify-between gap-3">
                  <h3 className="font-semibold">{q.name}</h3>
                  <QueueStatusBadge status={q.status} />
                </div>
                <p className="mt-1 text-xs text-ink-500">{q.service_name}</p>
                <div className="mt-3 flex flex-wrap gap-4 text-sm">
                  <span>{q.waiting_count} waiting</span>
                  <span>Serving {q.current_serving_label ?? "—"}</span>
                  <span>~{q.estimated_wait_minutes}m wait</span>
                </div>
              </Link>
            ))}
        </Card>
        <Card title="Weekly activity">
          {trends.data && <TrendChart data={trends.data.daily} />}
          <Link
            to="/staff/analytics"
            className="mt-5 inline-block text-sm font-semibold text-signal-700"
          >
            Explore analytics →
          </Link>
        </Card>
      </div>
    </AppShell>
  );
}
