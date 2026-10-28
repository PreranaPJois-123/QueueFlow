import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { AppShell } from "../../components/AppShell";
import { EmptyState, ErrorState, Skeleton } from "../../components/States";
import { PageHeader, StatusBadge, Tabs } from "../../components/ui";
import { api, extractErrorMessage } from "../../lib/api";
import { calendarDate, money, venueDate, venueTime } from "../../lib/format";
import { useRealtime } from "../../lib/realtime";
import type { Booking, Reservation } from "../../types";

type Scope = "upcoming" | "past";

export function BookingRow({ booking }: { booking: Booking }) {
  return (
    <li>
      <Link to={`/bookings/${booking.reference}`} className="flex flex-col gap-2 px-5 py-4 hover:bg-ink-50/60 sm:flex-row sm:items-center sm:gap-6">
        <div className="w-28 shrink-0">
          <p className="font-display text-lg font-semibold text-ink-900">{booking.token_label}</p>
          <p className="text-xs text-ink-400">{booking.reference}</p>
        </div>
        <div className="min-w-0 flex-1">
          <p className="font-medium text-ink-900">{booking.offering_name}</p>
          <p className="text-sm text-ink-500">{booking.provider_name}, {booking.venue_name}</p>
        </div>
        <div className="text-sm text-ink-700 sm:text-right">
          <p>{venueDate(booking.start_at, booking.venue_timezone)}</p>
          <p className="text-ink-500">{venueTime(booking.start_at, booking.venue_timezone)}</p>
        </div>
        <StatusBadge status={booking.status} />
      </Link>
    </li>
  );
}

export function ReservationRow({ reservation }: { reservation: Reservation }) {
  return (
    <li>
      <Link to={`/reservations/${reservation.reference}`} className="flex flex-col gap-2 px-5 py-4 hover:bg-ink-50/60 sm:flex-row sm:items-center sm:gap-6">
        <div className="w-28 shrink-0">
          <p className="font-display text-lg font-semibold text-stay-600">{reservation.nights} night{reservation.nights > 1 ? "s" : ""}</p>
          <p className="text-xs text-ink-400">{reservation.reference}</p>
        </div>
        <div className="min-w-0 flex-1">
          <p className="font-medium text-ink-900">{reservation.room_type_name}</p>
          <p className="text-sm text-ink-500">{reservation.venue_name}, {reservation.guests} guest{reservation.guests > 1 ? "s" : ""}</p>
        </div>
        <div className="text-sm text-ink-700 sm:text-right">
          <p>{calendarDate(reservation.check_in, { year: undefined })} to {calendarDate(reservation.check_out, { year: undefined })}</p>
          <p className="text-ink-500">{money(reservation.total, reservation.currency)}</p>
        </div>
        <StatusBadge status={reservation.status} />
      </Link>
    </li>
  );
}

export default function MyBookings() {
  const [params, setParams] = useSearchParams();
  const scope = (params.get("scope") as Scope) || "upcoming";
  const [bookings, setBookings] = useState<Booking[] | null>(null);
  const [reservations, setReservations] = useState<Reservation[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { subscribeBookings } = useRealtime();
  const [revision, setRevision] = useState(0);

  useEffect(() => subscribeBookings(() => setRevision((r) => r + 1)), [subscribeBookings]);

  useEffect(() => {
    setError(null);
    Promise.all([api.get<Booking[]>("/api/bookings", { params: { scope } }),
                 api.get<Reservation[]>("/api/reservations", { params: { scope } })])
      .then(([b, r]) => { setBookings(b.data); setReservations(r.data); })
      .catch((e) => setError(extractErrorMessage(e)));
  }, [scope, revision]);

  const loading = !error && (!bookings || !reservations);
  const empty = bookings && reservations && !bookings.length && !reservations.length;

  return (
    <AppShell>
      <PageHeader title="My bookings" description="Appointments with your queue token, and hotel reservations." />
      <Tabs label="Booking period" value={scope} onChange={(v) => setParams({ scope: v })}
        items={[{ value: "upcoming", label: "Upcoming" }, { value: "past", label: "Past and cancelled" }]} />
      {error && <ErrorState message={error} />}
      {loading && <div className="space-y-3"><Skeleton className="h-20" /><Skeleton className="h-20" /></div>}
      {empty && (
        <EmptyState title={scope === "upcoming" ? "No upcoming bookings" : "Nothing here yet"}
          body={scope === "upcoming" ? "Book a doctor, a shop service or a hotel room and it will appear here." : "Completed and cancelled bookings appear here."}
          action={scope === "upcoming" ? <div className="flex flex-wrap justify-center gap-2">
            <Link to="/hospitals" className="action-link">Find a hospital</Link>
            <Link to="/shops" className="action-link">Find a shop</Link>
            <Link to="/hotels" className="action-link">Find a hotel</Link></div> : undefined} />
      )}
      {!!bookings?.length && (
        <section className="mb-8">
          <h2 className="mb-3 text-base font-semibold text-ink-900">Appointments</h2>
          <ul className="divide-y divide-ink-100 overflow-hidden rounded-2xl border border-ink-100 bg-white">
            {bookings.map((b) => <BookingRow key={b.id} booking={b} />)}
          </ul>
        </section>
      )}
      {!!reservations?.length && (
        <section>
          <h2 className="mb-3 text-base font-semibold text-ink-900">Hotel stays</h2>
          <ul className="divide-y divide-ink-100 overflow-hidden rounded-2xl border border-ink-100 bg-white">
            {reservations.map((r) => <ReservationRow key={r.id} reservation={r} />)}
          </ul>
        </section>
      )}
    </AppShell>
  );
}
