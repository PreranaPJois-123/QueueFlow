import { kindMeta } from "../../lib/kinds";
import { useCallback, useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { AppShell } from "../../components/AppShell";
import { Button } from "../../components/Button";
import { EmptyState, ErrorState, Skeleton } from "../../components/States";
import { useToast } from "../../components/Toast";
import { DataTable, Modal, PageHeader, Panel, SampleTag, StatusBadge, TextField } from "../../components/ui";
import { api, extractErrorMessage } from "../../lib/api";
import { calendarDate, money, relativeMinutes, todayIn, venueTime } from "../../lib/format";
import type { Reservation, VenueSummary } from "../../types";

export function OpsVenueList() {
  const [venues, setVenues] = useState<VenueSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api.get<VenueSummary[]>("/api/ops/venues").then((r) => setVenues(r.data)).catch((e) => setError(extractErrorMessage(e)));
  }, []);
  return (
    <AppShell>
      <PageHeader title="Venue queues" description="Venues you're assigned to. Run today's appointment queues and the hotel front desk." />
      {error && <ErrorState message={error} />}
      {!venues && !error && <Skeleton className="h-40" />}
      {venues?.length === 0 && <EmptyState title="You're not assigned to any venue yet" body="An administrator can assign you from Administration, Venues, Staff." />}
      {!!venues?.length && (
        <ul className="divide-y divide-ink-100 overflow-hidden rounded-2xl border border-ink-100 bg-white">
          {venues.map((v) => (
            <li key={v.id}>
              <Link to={`/staff/venues/${v.id}`} className="flex items-center justify-between gap-4 px-5 py-4 hover:bg-ink-50/60">
                <div>
                  <p className="flex items-center gap-2 font-semibold text-ink-900">{v.name}{v.is_sample && <SampleTag />}</p>
                  <p className="text-sm text-ink-500">{kindMeta[v.kind].label}, {v.city}</p>
                </div>
                <span className="text-sm font-semibold text-ink-700">{v.kind === "HOTEL" ? "Front desk" : "Open queue"}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </AppShell>
  );
}

interface BoardBooking {
  id: string; reference: string; token_label: string; status: string; start_at: string; end_at: string;
  customer_name: string; offering_name: string; notes: string | null; position: number | null; eta_minutes: number | null;
}
interface ProviderQueue {
  provider_id: string; provider_name: string; provider_title: string; status: string; delay_minutes: number;
  current_token: string | null; waiting: number; bookings: BoardBooking[];
}

function AppointmentBoard({ venue, day }: { venue: VenueSummary; day: string }) {
  const { push } = useToast();
  const [providers, setProviders] = useState<ProviderQueue[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [delayFor, setDelayFor] = useState<ProviderQueue | null>(null);
  const [delayValue, setDelayValue] = useState("15");
  const isToday = day === todayIn(venue.timezone);

  const load = useCallback(async () => {
    try {
      const { data } = await api.get<{ providers: ProviderQueue[] }>(`/api/ops/venues/${venue.id}/queue`, { params: { date: day } });
      setProviders(data.providers);
      setError(null);
    } catch (e) {
      setError(extractErrorMessage(e));
    }
  }, [venue.id, day]);

  useEffect(() => {
    void load();
    const t = setInterval(() => void load(), 20000);
    return () => clearInterval(t);
  }, [load]);

  async function act(key: string, request: () => Promise<unknown>, done: string) {
    setBusy(key);
    try {
      await request();
      push(done, "success");
      await load();
    } catch (e) {
      push(extractErrorMessage(e), "error");
    } finally {
      setBusy(null);
    }
  }

  if (error) return <ErrorState message={error} />;
  if (!providers) return <Skeleton className="h-64" />;
  if (!providers.length) return <EmptyState title="No providers configured" body="An administrator needs to add doctors or staff to this venue." />;

  const busyProviders = providers.filter((p) => p.bookings.length > 0);
  const idle = providers.filter((p) => p.bookings.length === 0);
  const submitDelay = () => {
    const minutes = Number(delayValue);
    if (!delayFor) return;
    if (!Number.isInteger(minutes) || minutes < 0 || minutes > 600) return push("Enter whole minutes between 0 and 600", "error");
    const p = delayFor;
    setDelayFor(null);
    void act(`delay-${p.provider_id}`, () => api.post(`/api/ops/providers/${p.provider_id}/queue/${day}`, { delay_minutes: minutes }),
      minutes ? "Delay reported, customers notified" : "Delay cleared");
  };
  return (
    <div className="space-y-6">
      {busyProviders.length === 0 && <EmptyState title={`No appointments on ${calendarDate(day)}`} body="Bookings appear here as customers make them." />}
      {busyProviders.map((p) => {
        const active = p.bookings.filter((b) => ["CONFIRMED", "CHECKED_IN", "IN_SERVICE"].includes(b.status));
        const serving = p.bookings.find((b) => b.status === "IN_SERVICE");
        return (
          <Panel key={p.provider_id}>
            <div className="mb-4 flex flex-wrap items-start justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold text-ink-900">{p.provider_name}</h2>
                <p className="text-sm text-ink-500">{p.provider_title}</p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <StatusBadge status={p.status} />
                {p.delay_minutes > 0 && <span className="text-sm text-amber-600">{p.delay_minutes} min behind</span>}
              </div>
            </div>
            <div className="mb-4 grid gap-3 sm:grid-cols-3">
              <div className={`rounded-xl px-4 py-3 ${serving ? "bg-amber-100" : "bg-ink-50"}`}>
                <p className="text-xs text-ink-500">Now serving</p>
                <p className="font-display text-2xl font-semibold text-ink-900">{p.current_token || "None"}</p>
              </div>
              <div className="rounded-xl bg-ink-50 px-4 py-3">
                <p className="text-xs text-ink-500">Waiting</p>
                <p className="font-display text-2xl font-semibold text-ink-900">{p.waiting}</p>
              </div>
              <div className="flex flex-wrap items-center gap-2 rounded-xl bg-ink-50 px-4 py-3">
                <Button size="sm" disabled={!isToday || !!serving || !active.length || p.status === "PAUSED"} loading={busy === `next-${p.provider_id}`}
                  onClick={() => void act(`next-${p.provider_id}`, () => api.post(`/api/ops/providers/${p.provider_id}/queue/${day}/next`), "Next customer called")}>
                  Start next
                </Button>
                {p.bookings.length > 0 && (
                  <>
                    <Button size="sm" variant="secondary" loading={busy === `pause-${p.provider_id}`}
                      onClick={() => void act(`pause-${p.provider_id}`, () => api.post(`/api/ops/providers/${p.provider_id}/queue/${day}`, { paused: p.status !== "PAUSED" }), p.status === "PAUSED" ? "Queue resumed" : "Queue paused")}>
                      {p.status === "PAUSED" ? "Resume" : "Pause"}
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => { setDelayFor(p); setDelayValue(String(p.delay_minutes || 15)); }}>Report delay</Button>
                  </>
                )}
              </div>
            </div>
            <DataTable rows={p.bookings} rowKey={(b) => b.id}
              empty={<p className="rounded-xl border border-dashed border-ink-200 px-4 py-6 text-center text-sm text-ink-400">No bookings for {calendarDate(day)}.</p>}
              columns={[
                { header: "Token", cell: (b) => <span className="font-display font-semibold">{b.token_label}</span> },
                { header: "Time", cell: (b) => venueTime(b.start_at, venue.timezone) },
                { header: "Customer", cell: (b) => <><p className="font-medium text-ink-900">{b.customer_name}</p><p className="text-xs text-ink-500">{b.offering_name}</p>{b.notes && <p className="text-xs text-ink-500">Note: {b.notes}</p>}</> },
                { header: "Status", cell: (b) => <div><StatusBadge status={b.status} />{b.eta_minutes !== null && b.status !== "IN_SERVICE" && <p className="mt-1 text-xs text-ink-400">#{b.position}, ~{relativeMinutes(b.eta_minutes)}</p>}</div> },
                { header: "Actions", cell: (b) => (
                  <div className="flex flex-wrap gap-1.5">
                    {b.status === "CONFIRMED" && isToday && <Button size="sm" variant="secondary" loading={busy === b.id + "check-in"} onClick={() => void act(b.id + "check-in", () => api.post(`/api/ops/bookings/${b.id}/check-in`), `${b.token_label} checked in`)}>Check in</Button>}
                    {["CONFIRMED", "CHECKED_IN"].includes(b.status) && isToday && !serving && <Button size="sm" loading={busy === b.id + "start"} onClick={() => void act(b.id + "start", () => api.post(`/api/ops/bookings/${b.id}/start`), `${b.token_label} called`)}>Start</Button>}
                    {b.status === "IN_SERVICE" && <Button size="sm" loading={busy === b.id + "complete"} onClick={() => void act(b.id + "complete", () => api.post(`/api/ops/bookings/${b.id}/complete`), `${b.token_label} completed`)}>Complete</Button>}
                    {["CONFIRMED", "CHECKED_IN"].includes(b.status) && <Button size="sm" variant="ghost" loading={busy === b.id + "no-show"} onClick={() => void act(b.id + "no-show", () => api.post(`/api/ops/bookings/${b.id}/no-show`), `${b.token_label} marked as no-show`)}>No-show</Button>}
                  </div>
                ) },
              ]} />
          </Panel>
        );
      })}
      {idle.length > 0 && (
        <p className="text-sm text-ink-500">No bookings on {calendarDate(day)} for {idle.map((p) => p.provider_name).join(", ")}.</p>
      )}
      <Modal open={!!delayFor} title={`Report delay for ${delayFor?.provider_name ?? ""}`} onClose={() => setDelayFor(null)}
        footer={<><Button variant="secondary" onClick={() => setDelayFor(null)}>Cancel</Button><Button onClick={submitDelay}>Save delay</Button></>}>
        <TextField label="Minutes behind schedule" type="number" min={0} max={600} value={delayValue}
          hint="Waiting customers are notified once per new value. Enter 0 to clear." onChange={(e) => setDelayValue(e.target.value)} />
      </Modal>
    </div>
  );
}

function FrontDesk({ venue, day }: { venue: VenueSummary; day: string }) {
  const { push } = useToast();
  const [items, setItems] = useState<(Reservation & { guest_name: string })[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const load = useCallback(() => {
    api.get(`/api/ops/venues/${venue.id}/reservations`, { params: { date: day } })
      .then((r) => { setItems(r.data.items); setError(null); }).catch((e) => setError(extractErrorMessage(e)));
  }, [venue.id, day]);
  useEffect(load, [load]);

  async function act(id: string, action: string, label: string) {
    setBusy(id + action);
    try {
      await api.post(`/api/ops/reservations/${id}/${action}`);
      push(label, "success");
      load();
    } catch (e) {
      push(extractErrorMessage(e), "error");
    } finally {
      setBusy(null);
    }
  }

  if (error) return <ErrorState message={error} />;
  if (!items) return <Skeleton className="h-48" />;
  return (
    <DataTable rows={items} rowKey={(r) => r.id}
      empty={<EmptyState title={`No stays on ${calendarDate(day)}`} body="Reservations covering this date appear here." />}
      columns={[
        { header: "Guest", cell: (r) => <><p className="font-medium text-ink-900">{r.guest_name}</p><p className="text-xs text-ink-500">{r.reference}</p></> },
        { header: "Room", cell: (r) => `${r.room_type_name}${r.rooms > 1 ? ` x ${r.rooms}` : ""}, ${r.guests} guest${r.guests > 1 ? "s" : ""}` },
        { header: "Stay", cell: (r) => `${calendarDate(r.check_in, { year: undefined })} to ${calendarDate(r.check_out, { year: undefined })}` },
        { header: "Total", cell: (r) => money(r.total, r.currency) },
        { header: "Status", cell: (r) => <StatusBadge status={r.status} /> },
        { header: "Actions", cell: (r) => (
          <div className="flex flex-wrap gap-1.5">
            {r.status === "CONFIRMED" && r.check_in <= day && <Button size="sm" loading={busy === r.id + "check-in"} onClick={() => void act(r.id, "check-in", "Guest checked in")}>Check in</Button>}
            {r.status === "CHECKED_IN" && <Button size="sm" loading={busy === r.id + "check-out"} onClick={() => void act(r.id, "check-out", "Guest checked out")}>Check out</Button>}
            {r.status === "CONFIRMED" && r.check_in <= day && <Button size="sm" variant="ghost" loading={busy === r.id + "no-show"} onClick={() => void act(r.id, "no-show", "Marked as no-show; remaining nights released")}>No-show</Button>}
          </div>
        ) },
      ]} />
  );
}

export function OpsVenueBoard() {
  const { id } = useParams();
  const [params, setParams] = useSearchParams();
  const [venue, setVenue] = useState<VenueSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api.get(`/api/ops/venues/${id}/queue`).then((r) => setVenue(r.data.venue)).catch((e) => setError(extractErrorMessage(e)));
  }, [id]);
  if (error) return <AppShell><ErrorState message={error} /></AppShell>;
  if (!venue) return <AppShell><Skeleton className="h-64" /></AppShell>;
  const day = params.get("date") || todayIn(venue.timezone);
  return (
    <AppShell>
      <PageHeader back={{ to: "/staff/venues", label: "Venue queues" }} title={venue.name}
        description={venue.kind === "HOTEL" ? "Front desk: arrivals and in-house guests." : "Appointment queues by provider. Refreshes every 20 seconds."}
        actions={<div className="flex items-center gap-2">
          <label htmlFor="ops-date" className="text-sm text-ink-500">Date</label>
          <input id="ops-date" type="date" className="field w-auto" value={day} onChange={(e) => setParams({ date: e.target.value })} />
        </div>} />
      {venue.kind === "HOTEL" ? <FrontDesk venue={venue} day={day} /> : <AppointmentBoard venue={venue} day={day} />}
    </AppShell>
  );
}
