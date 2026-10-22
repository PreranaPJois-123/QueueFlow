import { AppShell } from "../../components/AppShell";
import {
  Heading,
  Card,
  Metric,
  ResourceState,
  TrendChart,
} from "../../components/Product";

import { useResource } from "../../lib/useResource";
import type { Analytics, Trends, QueueSummary } from "../../types";
export default function AnalyticsPage() {
  const analytics = useResource<Analytics>("/api/analytics");
  const trends = useResource<Trends>("/api/product/trends");
  const queues = useResource<QueueSummary[]>("/api/product/queues");
  return (
    <AppShell variant="staff">
      <Heading
        title="Service analytics"
        body="Actual visits, outcomes, and recorded durations. Daily boundaries use UTC."
      />
      <ResourceState {...analytics} />
      <ResourceState {...trends} />
      <ResourceState {...queues} />
      {analytics.data && trends.data && (
        <>
          <div className="my-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {[
              ["Total tickets", trends.data.total_tickets],
              ["Customers served", trends.data.total_served],
              ["Completion rate", `${trends.data.completion_rate}%`],
              ["Skip rate", `${trends.data.skip_rate}%`],
              ["Average wait", `${analytics.data.average_wait_minutes} min`],
              [
                "Average service",
                `${analytics.data.average_service_minutes} min`,
              ],
              ["Appointments", trends.data.appointments],
              ["Open queues", analytics.data.active_queues],
            ].map(([label, value]) => (
              <Metric key={label} label={String(label)} value={value} />
            ))}
          </div>
          <div className="grid gap-6 lg:grid-cols-2">
            <Card title="Seven-day trend">
              <TrendChart data={trends.data.daily} />
            </Card>
            <Card title="Queue utilization">
              <p className="mb-4 text-xs text-ink-500">
                Current queue load; this is a snapshot, not historical capacity.
              </p>
              {queues.data?.map((q) => (
                <div key={q.id} className="border-b border-ink-100 py-3">
                  <p className="text-sm font-semibold">{q.name}</p>
                  <p className="mt-1 text-xs text-ink-500">
                    {q.waiting_count} waiting ·{" "}
                    {q.current_serving_label
                      ? "1 active visit"
                      : "No active visit"}{" "}
                    · {q.status.toLowerCase()}
                  </p>
                </div>
              ))}
              <p className="mt-5 text-sm">
                Busiest arrival hour:{" "}
                {analytics.data.busiest_hour === null
                  ? "No history yet"
                  : `${String(analytics.data.busiest_hour).padStart(2, "0")}:00 UTC`}
              </p>
            </Card>
          </div>
          <p className="mt-5 text-xs text-ink-500">
            Completion and skip rates use all created tickets as the
            denominator. Averages use completed service records; active visits
            have no completed duration yet.
          </p>
        </>
      )}
    </AppShell>
  );
}
