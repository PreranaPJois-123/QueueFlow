import { useCallback, useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { AppShell } from "../../components/AppShell";
import { Button } from "../../components/Button";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { EmptyState, ErrorState, Skeleton } from "../../components/States";
import { TokenStub } from "../../components/TokenStub";
import { useToast } from "../../components/Toast";
import { Modal, PageHeader, Panel } from "../../components/ui";
import { api, extractErrorMessage } from "../../lib/api";
import { addDays, dateTime, todayIn, venueTime } from "../../lib/format";
import { useRealtime } from "../../lib/realtime";
import type { Booking, Slot } from "../../types";

function Reschedule({ booking, open, onClose, onDone }: {
  booking: Booking; open: boolean; onClose: () => void; onDone: (b: Booking) => void;
}) {
  const [day, setDay] = useState(booking.service_date);
  const [slots, setSlots] = useState<Slot[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState<string | null>(null);
  useEffect(() => {
    if (!open) return;
    setSlots(null);
    setError(null);
    api.get<Slot[]>(`/api/venues/${booking.venue_id}/slots`, { params: { offering_id: booking.offering_id, date: day,
      provider_id: booking.provider_id } }).then((r) => setSlots(r.data)).catch((e) => setError(extractErrorMessage(e)));
  }, [open, day, booking]);

  async function choose(slot: Slot) {
    setSaving(slot.start_at);
    try {
      const { data } = await api.post<Booking>(`/api/bookings/${booking.reference}/reschedule`, { start_at: slot.start_at });
      onDone(data);
    } catch (e) {
      setError(extractErrorMessage(e));
    } finally {
      setSaving(null);
    }
  }

  const today = todayIn(booking.venue_timezone);
  return (
    <Modal open={open} onClose={onClose} title="Choose a new time" wide>
      <p className="mb-4 text-sm text-ink-500">Same service with {booking.provider_name}. Moving to another day gives you a new token for that day.</p>
      <label className="label" htmlFor="reschedule-date">Date</label>
      <input id="reschedule-date" type="date" className="field mb-4 mt-1.5 max-w-xs" min={today} max={addDays(today, 60)}
        value={day} onChange={(e) => setDay(e.target.value)} />
      {error && <ErrorState message={error} />}
      {!slots && !error && <Skeleton className="h-16" />}
      {slots && slots.length === 0 && <EmptyState title="No free times that day" body="Try another date." />}
      {slots && slots.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {slots.map((s) => (
            <Button key={s.start_at} variant="secondary" size="sm" loading={saving === s.start_at} disabled={!!saving}
              onClick={() => void choose(s)}>{venueTime(s.start_at, booking.venue_timezone)}</Button>
          ))}
        </div>
      )}
    </Modal>
  );
}

export default function BookingDetail() {
  const { reference } = useParams();
  const [params] = useSearchParams();
  const isNew = params.get("new") === "1";
  const { push } = useToast();
  const { subscribeBookings, connected } = useRealtime();
  const [booking, setBooking] = useState<Booking | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cancelOpen, setCancelOpen] = useState(false);
  const [moveOpen, setMoveOpen] = useState(false);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);

  const load = useCallback(async () => {
    try {
      const { data } = await api.get<Booking>(`/api/bookings/${reference}`);
      setBooking(data);
      setUpdatedAt(new Date());
      setError(null);
    } catch (e) {
      setError(extractErrorMessage(e));
    }
  }, [reference]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => subscribeBookings((u) => {
    if (u.reference !== reference) return;
    setBooking((b) => b && ({ ...b, status: u.status as Booking["status"], live: {
      queue_status: u.queue_status as "OPEN" | "PAUSED", current_token: u.current_token, delay_minutes: u.delay_minutes,
      position: u.position, eta_minutes: u.eta_minutes, expected_start: b.live?.expected_start ?? null } }));
    setUpdatedAt(new Date());
  }), [subscribeBookings, reference]);

  // Fallback refresh when the live connection is unavailable.
  useEffect(() => {
    if (connected) return;
    const t = setInterval(() => void load(), 30000);
    return () => clearInterval(t);
  }, [connected, load]);

  async function cancel() {
    try {
      const { data } = await api.post<Booking>(`/api/bookings/${reference}/cancel`);
      setBooking(data);
      push("Booking cancelled", "success");
    } catch (e) {
      push(extractErrorMessage(e), "error");
    } finally {
      setCancelOpen(false);
    }
  }

  if (error && !booking) return <AppShell><ErrorState message={error} /><Link to="/bookings" className="action-link mt-4">Back to my bookings</Link></AppShell>;
  if (!booking) return <AppShell><Skeleton className="h-64" /></AppShell>;
  const active = ["CONFIRMED", "CHECKED_IN", "IN_SERVICE"].includes(booking.status);

  return (
    <AppShell>
      <PageHeader back={{ to: "/bookings", label: "My bookings" }}
        title={isNew ? "You're booked" : "Appointment"}
        description={isNew ? `Keep your token handy. We'll notify you when your turn is about 20 minutes away.` : undefined} />
      <TokenStub booking={booking} footer={booking.notes ? <p className="text-sm text-ink-500">Note: {booking.notes}</p> : undefined} />
      {active && (
        <p className="mt-3 text-xs text-ink-400" aria-live="polite">
          {connected ? "Live updates on" : "Live connection unavailable, refreshing every 30 seconds"}
          {updatedAt && `. Updated ${updatedAt.toLocaleTimeString()}`}
        </p>
      )}
      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Panel title="Manage">
          {booking.can_cancel ? (
            <div className="flex flex-wrap gap-2">
              <Button variant="secondary" onClick={() => setMoveOpen(true)}>Reschedule</Button>
              <Button variant="danger" onClick={() => setCancelOpen(true)}>Cancel booking</Button>
            </div>
          ) : (
            <p className="text-sm text-ink-500">
              {active ? `Online changes close ${booking.cancel_cutoff_minutes} minutes before the appointment. Contact ${booking.venue_name} for help.`
                : "This booking can no longer be changed."}
            </p>
          )}
          <p className="mt-4 text-xs text-ink-400">Booked {dateTime(booking.created_at)}</p>
        </Panel>
        <Panel title="On the day">
          <ul className="space-y-2 text-sm text-ink-600">
            <li>Show token <span className="font-semibold text-ink-900">{booking.token_label}</span> at the {booking.venue_kind === "HOSPITAL" ? "reception desk" : "counter"}.</li>
            <li>Wait estimates update as the queue moves; they aren't guarantees.</li>
            {booking.venue_kind === "HOSPITAL" && <li>In an emergency, don't wait for your slot: call 112 or go to the emergency department.</li>}
          </ul>
          <Link to={`/venues/${booking.venue_id}`} className="action-link mt-4">View {booking.venue_name}</Link>
        </Panel>
      </div>
      <ConfirmDialog open={cancelOpen} danger title="Cancel this appointment?" confirmLabel="Cancel booking"
        body={`Your slot and token ${booking.token_label} will be released. This can't be undone.`}
        onConfirm={cancel} onCancel={() => setCancelOpen(false)} />
      <Reschedule booking={booking} open={moveOpen} onClose={() => setMoveOpen(false)}
        onDone={(b) => { setBooking(b); setMoveOpen(false); push("Appointment rescheduled", "success"); }} />
    </AppShell>
  );
}
