import { useState } from "react";
import { AppShell } from "../../components/AppShell";
import {
  Card,
  Heading,
  ResourceState,
  TicketHistory,
} from "../../components/Product";
import { activeStatus, dateTime } from "../../lib/format";
import { Button } from "../../components/Button";
import { EmptyState } from "../../components/States";
import { useResource } from "../../lib/useResource";
import type { CustomerRecord } from "../../types";
export default function Customers() {
  const resource = useResource<CustomerRecord[]>("/api/product/customers");
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const [selected, setSelected] = useState<string | null>(null);
  const customers =
    resource.data?.filter(
      (c) =>
        `${c.full_name} ${c.email}`
          .toLowerCase()
          .includes(search.toLowerCase()) &&
        (filter === "all" || c.tickets.some((t) => activeStatus(t.status))),
    ) ?? [];
  const customer = resource.data?.find((c) => c.id === selected);
  return (
    <AppShell variant="staff">
      <Heading
        title="Customers"
        body="Customer records, current tickets, and visit history."
      />
      <div className="my-6 flex flex-wrap gap-3">
        <input
          className="field max-w-sm"
          aria-label="Search customers"
          placeholder="Search name or email…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select
          className="field max-w-xs"
          aria-label="Customer filter"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        >
          <option value="all">All customers</option>
          <option value="active">Active tickets</option>
        </select>
      </div>
      <ResourceState {...resource} />
      {resource.data && !customers.length && (
        <EmptyState
          title="No customers found"
          body="Customer registrations will appear here. Try a different filter."
        />
      )}
      <div className="grid gap-4 lg:grid-cols-2">
        {customers.map((c) => (
          <Card key={c.id}>
            <div className="flex flex-wrap justify-between gap-3">
              <div>
                <h2 className="font-semibold">{c.full_name}</h2>
                <p className="mt-1 break-all text-xs text-ink-500">{c.email}</p>
              </div>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setSelected(selected === c.id ? null : c.id)}
              >
                View details
              </Button>
            </div>
            <p className="mt-4 text-sm text-ink-500">
              {c.tickets
                .filter((t) => activeStatus(t.status))
                .map((t) => `${t.token_label} · ${t.queue_name}`)
                .join(" / ") || "No active tickets"}
            </p>
            <p className="mt-2 text-xs text-ink-500">
              {c.tickets.length} tickets · {c.appointments.length} appointments
            </p>
          </Card>
        ))}
      </div>
      {customer && (
        <Card title={`${customer.full_name} · visit history`} className="mt-6">
          <TicketHistory staff tickets={customer.tickets} />
          <h3 className="mb-3 mt-6 font-semibold">Appointments</h3>
          {customer.appointments.length ? (
            customer.appointments.map((a) => (
              <p key={a.id} className="border-b border-ink-100 py-3 text-sm">
                {a.service_name} · {dateTime(a.scheduled_time)} ·{" "}
                {a.status.replaceAll("_", " ")}
              </p>
            ))
          ) : (
            <p className="text-sm text-ink-500">No appointments.</p>
          )}
        </Card>
      )}
    </AppShell>
  );
}
