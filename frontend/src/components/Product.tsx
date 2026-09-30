import { Link } from "react-router-dom";
import type { ReactNode } from "react";
import type { NamedTicket, Trends } from "../types";
import { TicketStatusBadge } from "./Badge";
import { Button } from "./Button";
import { ErrorState, Skeleton, EmptyState } from "./States";

import { dateTime } from "../lib/format";
export function Heading({
  title,
  body,
  action,
}: {
  title: string;
  body?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-4">
      <div>
        <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-signal-700">
          QueueFlow workspace
        </p>
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">
          {title}
        </h1>
        {body && <p className="mt-2 text-sm text-ink-500">{body}</p>}
      </div>
      {action}
    </div>
  );
}
export function Card({
  title,
  children,
  className = "",
}: {
  title?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`rounded-2xl border border-ink-100 bg-white p-5 shadow-sm sm:p-6 ${className}`}
    >
      {title && <h2 className="mb-4 text-base font-semibold">{title}</h2>}
      {children}
    </section>
  );
}
export function Metric({
  label,
  value,
  note,
}: {
  label: string;
  value: number | string;
  note?: string;
}) {
  return (
    <Card>
      <p className="text-xs font-medium text-ink-500">{label}</p>
      <p className="mt-2 text-3xl font-bold tabular-nums">{value}</p>
      {note && <p className="mt-2 text-xs text-ink-500">{note}</p>}
    </Card>
  );
}
export function ResourceState({
  loading,
  error,
  refresh,
}: {
  loading: boolean;
  error: string | null;
  refresh: () => void;
}) {
  return (
    <>
      {error && (
        <div className="my-5 space-y-2">
          <ErrorState message={`${error} Displayed data may be out of date.`} />
          <Button variant="secondary" size="sm" onClick={refresh}>
            Retry
          </Button>
        </div>
      )}
      {loading && (
        <div className="my-6 grid gap-4 sm:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-36" />
          ))}
        </div>
      )}
    </>
  );
}
export function Connection({ status }: { status: string }) {
  return (
    <span
      role="status"
      className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold ${status === "LIVE" ? "bg-signal-50 text-signal-700" : "bg-amber-100 text-amber-600"}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {status}
    </span>
  );
}
export function TicketHistory({
  tickets,
  staff = false,
}: {
  tickets: NamedTicket[];
  staff?: boolean;
}) {
  return tickets.length ? (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[540px] text-left text-sm">
        <thead>
          <tr className="border-b border-ink-100 text-xs text-ink-500">
            <th className="py-3">Ticket</th>
            <th>Service / queue</th>
            <th>Joined</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {tickets.map((t) => (
            <tr key={t.id} className="border-b border-ink-50">
              <td className="py-4 font-semibold">
                <Link
                  to={
                    staff
                      ? `/staff/queue/${t.queue_id}`
                      : `/my-ticket?ticket=${t.id}`
                  }
                  className="text-signal-700"
                >
                  {t.token_label}
                </Link>
              </td>
              <td>
                {t.service_name}
                <p className="text-xs text-ink-500">{t.queue_name}</p>
              </td>
              <td className="text-xs text-ink-500">{dateTime(t.created_at)}</td>
              <td>
                <TicketStatusBadge status={t.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  ) : (
    <EmptyState
      title="No ticket history yet"
      body="Your visits appear here after joining a queue."
    />
  );
}
export function TrendChart({ data }: { data: Trends["daily"] }) {
  const max = Math.max(1, ...data.map((d) => Math.max(d.tickets, d.served)));
  return (
    <>
      <p className="mb-4 text-xs text-ink-500">
        Last seven days · UTC · arrivals and completed visits
      </p>
      <div
        className="flex h-48 items-end gap-2 sm:gap-5"
        role="img"
        aria-label="Daily arrivals and completed visits"
      >
        <div className="sr-only">
          {data
            .map(
              (d) => `${d.date}: ${d.tickets} arrivals, ${d.served} completed`,
            )
            .join("; ")}
        </div>
        {data.map((d) => (
          <div key={d.date} className="flex h-full flex-1 flex-col justify-end">
            <div className="flex h-36 items-end gap-1">
              <div
                title={`${d.tickets} arrivals`}
                className="flex-1 rounded-t bg-ink-200"
                style={{
                  height: `${(d.tickets / max) * 100}%`,
                  minHeight: d.tickets ? 3 : 0,
                }}
              />
              <div
                title={`${d.served} completed`}
                className="flex-1 rounded-t bg-signal-600"
                style={{
                  height: `${(d.served / max) * 100}%`,
                  minHeight: d.served ? 3 : 0,
                }}
              />
            </div>
            <p className="mt-3 text-center text-[10px] text-ink-500">
              {d.date.slice(5)}
            </p>
            <p className="mt-1 text-center text-[10px] text-ink-500">
              {d.tickets} / {d.served}
            </p>
          </div>
        ))}
      </div>
      <div className="mt-3 flex gap-4 text-xs text-ink-500">
        <span>■ Arrivals</span>
        <span className="text-signal-700">■ Completed</span>
      </div>
    </>
  );
}
