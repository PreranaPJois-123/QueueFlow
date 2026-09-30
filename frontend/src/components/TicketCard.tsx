import type { TicketDetail } from "../types";
import { Card, Connection } from "./Product";
import { predictionLabel, dateTime } from "../lib/format";
import { QueueStatusBadge, TicketStatusBadge } from "./Badge";
export function TicketCard({
  detail,
  connection,
}: {
  detail: TicketDetail;
  connection: string;
}) {
  const { ticket } = detail;
  return (
    <Card className="border-t-4 border-t-signal-600">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium text-ink-500">
            {detail.service_name} · {detail.queue_name}
          </p>
          <p className="token-display mt-3 text-6xl font-bold">
            {ticket.token_label}
          </p>
          <p className="mt-2 text-xs text-ink-500">
            Joined {dateTime(ticket.created_at)}
          </p>
        </div>
        <div className="flex flex-col items-end gap-2">
          <TicketStatusBadge status={ticket.status} />
          <Connection status={connection} />
          <QueueStatusBadge status={detail.queue_status} />
        </div>
      </div>
      <div
        className="mt-6 rounded-xl bg-signal-50 p-4 text-sm text-signal-700"
        role="status"
      >
        {ticket.status === "CALLED"
          ? "Your ticket has been called. Please proceed to the counter."
          : ticket.status === "SERVING"
            ? "Your service is in progress."
            : ticket.status === "SERVED"
              ? "Your visit is complete. Thank you!"
              : ticket.status === "SKIPPED"
                ? "This ticket was skipped. Contact the service desk if you need assistance."
                : ticket.status === "CANCELLED"
                  ? "This ticket was cancelled."
                  : detail.queue_status === "PAUSED"
                    ? "The queue is paused. Wait estimates exclude the pause duration."
                    : detail.smart_alert
                      ? "Your turn is approaching. Please be ready."
                      : "Your place is reserved. Follow this page for updates."}
      </div>
      <dl className="mt-6 grid grid-cols-2 gap-5 border-t border-ink-100 pt-5 sm:grid-cols-4">
        {[
          [
            "Position",
            ticket.status === "WAITING" ? detail.people_ahead + 1 : "—",
          ],
          ["People ahead", detail.people_ahead],
          [
            "Estimated wait",
            ticket.status === "WAITING"
              ? `~${detail.estimated_wait_minutes} min`
              : "—",
          ],
          ["Now serving", detail.current_serving_label ?? "—"],
        ].map(([label, value]) => (
          <div key={label}>
            <dt className="text-xs text-ink-500">{label}</dt>
            <dd className="mt-2 text-xl font-semibold">{value}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-5 text-xs text-ink-500">
        {predictionLabel(detail.prediction_source)} ·{" "}
        {detail.prediction_samples} completed records. Estimates may change.
      </p>
    </Card>
  );
}
