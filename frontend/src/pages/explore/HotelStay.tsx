import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Button } from "../../components/Button";
import { EmptyState, ErrorState, Skeleton } from "../../components/States";
import { Modal, Panel, TextAreaField, TextField } from "../../components/ui";
import { api, extractErrorMessage, newIdempotencyKey } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { addDays, calendarDate, dateTime, money, todayIn } from "../../lib/format";
import { validateStay } from "../../lib/booking";
import type { Quote, Reservation, VenueDetail } from "../../types";

export default function HotelStay({ venue }: { venue: VenueDetail }) {
  const { user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const today = todayIn(venue.timezone);
  const [checkIn, setCheckIn] = useState(addDays(today, 1));
  const [checkOut, setCheckOut] = useState(addDays(today, 3));
  const [guests, setGuests] = useState(2);
  const [rooms, setRooms] = useState(1);
  const [errors, setErrors] = useState<ReturnType<typeof validateStay>>({});
  const [quotes, setQuotes] = useState<Quote[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Quote | null>(null);
  const [requests, setRequests] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [confirmError, setConfirmError] = useState<string | null>(null);
  const idempotency = useMemo(() => (selected ? newIdempotencyKey() : ""), [selected]);

  async function search(e?: FormEvent) {
    e?.preventDefault();
    const found = validateStay(checkIn, checkOut, guests, today);
    setErrors(found);
    if (Object.keys(found).length) return;
    setLoading(true);
    setError(null);
    try {
      const { data } = await api.get<Quote[]>(`/api/venues/${venue.id}/rooms`, {
        params: { check_in: checkIn, check_out: checkOut, guests, rooms } });
      setQuotes(data);
    } catch (failure) {
      setError(extractErrorMessage(failure));
      setQuotes(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void search();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  function choose(q: Quote) {
    if (!user) {
      navigate("/login", { state: { from: location } });
      return;
    }
    setConfirmError(null);
    setSelected(q);
  }

  async function confirm() {
    if (!selected) return;
    setSubmitting(true);
    setConfirmError(null);
    try {
      const { data } = await api.post<Reservation>("/api/reservations", {
        venue_id: venue.id, room_type_id: selected.room_type_id, check_in: selected.check_in,
        check_out: selected.check_out, guests: selected.guests, rooms: selected.rooms,
        special_requests: requests.trim() || null,
      }, { headers: { "Idempotency-Key": idempotency } });
      navigate(`/reservations/${data.reference}?new=1`);
    } catch (failure) {
      setConfirmError(extractErrorMessage(failure));
      void search();
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <Panel title="Your stay">
        <form onSubmit={search} noValidate className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4 xl:items-start">
          <TextField label="Check-in" type="date" min={today} value={checkIn} error={errors.checkIn}
            onChange={(e) => { setCheckIn(e.target.value); if (e.target.value >= checkOut) setCheckOut(addDays(e.target.value, 1)); }} />
          <TextField label="Check-out" type="date" min={addDays(checkIn || today, 1)} value={checkOut} error={errors.checkOut}
            onChange={(e) => setCheckOut(e.target.value)} />
          <TextField label="Guests" type="number" min={1} max={20} value={guests} error={errors.guests}
            onChange={(e) => setGuests(Number(e.target.value))} />
          <TextField label="Rooms" type="number" min={1} max={5} value={rooms}
            onChange={(e) => setRooms(Math.min(5, Math.max(1, Number(e.target.value) || 1)))} />
          <div className="sm:col-span-2 xl:col-span-4"><Button type="submit" loading={loading}>Check availability</Button></div>
        </form>
      </Panel>
      <Panel title="Rooms">
        {error && <ErrorState message={error} />}
        {loading && !quotes && <div className="space-y-3"><Skeleton className="h-24" /><Skeleton className="h-24" /></div>}
        {quotes && quotes.length === 0 && (
          <EmptyState title="No room type fits this party" body="Try fewer guests per room, or add another room." />
        )}
        {quotes && quotes.length > 0 && (
          <ul className="divide-y divide-ink-100">
            {quotes.map((q) => {
              const room = venue.room_types.find((r) => r.id === q.room_type_id);
              return (
                <li key={q.room_type_id} className="flex flex-col gap-4 py-4 sm:flex-row sm:items-center sm:justify-between">
                  <div className="min-w-0">
                    <p className="font-semibold text-ink-900">{q.room_type_name}</p>
                    <p className="mt-0.5 text-sm text-ink-500">Sleeps {room?.max_occupancy}. {room?.amenities}</p>
                    <p className="mt-1 text-sm text-ink-600">
                      {money(q.nightly_rate, q.currency)} x {q.nights} night{q.nights > 1 ? "s" : ""}{q.rooms > 1 ? ` x ${q.rooms} rooms` : ""} + {money(q.taxes, q.currency)} taxes
                    </p>
                    <p className={`mt-1 text-xs font-medium ${q.available ? (q.rooms_left <= 2 ? "text-amber-600" : "text-signal-700") : "text-rose-600"}`}>
                      {q.available ? (q.rooms_left <= 2 ? `Only ${q.rooms_left} left for these dates` : "Available") : "Sold out for at least one night"}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-4 sm:flex-col sm:items-end sm:gap-2">
                    <p className="font-display text-xl font-semibold text-ink-900">{money(q.total, q.currency)}</p>
                    <Button disabled={!q.available} onClick={() => choose(q)}>Reserve</Button>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </Panel>
      <Modal open={!!selected} title="Review your reservation" onClose={() => !submitting && setSelected(null)}
        footer={<>
          <Button variant="secondary" onClick={() => setSelected(null)} disabled={submitting}>Back</Button>
          <Button onClick={() => void confirm()} loading={submitting}>Confirm reservation</Button>
        </>}>
        {selected && (
          <div className="space-y-4 text-sm">
            {venue.is_sample && <p className="text-ink-500">Sample listing: no real hotel receives this reservation.</p>}
            <dl className="space-y-2">
              {[["Hotel", venue.name], ["Room", `${selected.room_type_name}${selected.rooms > 1 ? ` x ${selected.rooms}` : ""}`],
                ["Check-in", calendarDate(selected.check_in)], ["Check-out", calendarDate(selected.check_out)],
                ["Guests", String(selected.guests)], ["Room charge", money(selected.subtotal, selected.currency)],
                ["Taxes", money(selected.taxes, selected.currency)]].map(([k, v]) => (
                <div key={k} className="flex justify-between gap-4"><dt className="text-ink-500">{k}</dt><dd className="text-right font-medium text-ink-800">{v}</dd></div>
              ))}
              <div className="flex justify-between gap-4 border-t border-ink-100 pt-2 text-base">
                <dt className="font-semibold text-ink-900">Total</dt>
                <dd className="font-display font-semibold text-ink-900">{money(selected.total, selected.currency)}</dd>
              </div>
            </dl>
            <p className="text-ink-500">Free cancellation until {dateTime(selected.free_cancellation_until)}. Payment is made at the hotel; QueueFlow never asks for card details.</p>
            <TextAreaField label="Special requests (optional)" maxLength={500} value={requests} onChange={(e) => setRequests(e.target.value)} />
            {confirmError && <ErrorState message={confirmError} />}
          </div>
        )}
      </Modal>
    </>
  );
}
