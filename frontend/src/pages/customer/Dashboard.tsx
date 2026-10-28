import { kindMeta } from "../../lib/kinds";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { AppShell } from "../../components/AppShell";
import { ErrorState, Skeleton } from "../../components/States";
import { TokenStub } from "../../components/TokenStub";
import { api, extractErrorMessage } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { useRealtime } from "../../lib/realtime";
import type { Booking, Reservation, VenueKind } from "../../types";
import { BookingRow, ReservationRow } from "../bookings/MyBookings";

const PLACES: { kind: VenueKind; line: string }[] = [
  { kind: "HOSPITAL", line: "Doctor consultations with a queue token" },
  { kind: "SHOP", line: "Salons, repairs and consultations" },
  { kind: "HOTEL", line: "Rooms with the price shown upfront" },
];

export default function CustomerDashboard() {
  const { user } = useAuth();
  const { subscribeBookings, unread } = useRealtime();
  const [bookings, setBookings] = useState<Booking[] | null>(null);
  const [reservations, setReservations] = useState<Reservation[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);

  useEffect(() => subscribeBookings(() => setRevision((r) => r + 1)), [subscribeBookings]);
  useEffect(() => {
    Promise.all([api.get<Booking[]>("/api/bookings"), api.get<Reservation[]>("/api/reservations")])
      .then(([b, r]) => { setBookings(b.data); setReservations(r.data); setError(null); })
      .catch((e) => setError(extractErrorMessage(e)));
  }, [revision]);

  const next = bookings?.[0];
  const firstName = user?.full_name.split(" ")[0];

  return (
    <AppShell>
      <section className="relative mb-10 overflow-hidden rounded-3xl bg-night px-6 py-8 text-white md:px-10 md:py-10">
        <div aria-hidden className="absolute -right-16 -top-20 h-64 w-64 rounded-full bg-serving/20 blur-3xl" />
        <p className="text-sm text-ink-300">{new Intl.DateTimeFormat("en-IN", { weekday: "long", day: "numeric", month: "long" }).format(new Date())}</p>
        <h1 className="mt-1 text-3xl font-semibold md:text-4xl">Hello, {firstName}</h1>
        <p className="mt-2 max-w-xl text-ink-300">Your next visit, live queue position and everything you've booked, in one place.</p>
        <dl className="mt-8 grid max-w-xl grid-cols-3 gap-3">
          {[["Appointments", bookings?.length], ["Hotel stays", reservations?.length], ["Unread alerts", unread]].map(([label, value]) => (
            <div key={String(label)} className="rounded-2xl bg-white/5 px-4 py-3 ring-1 ring-white/10">
              <dt className="text-xs text-ink-300">{label}</dt>
              <dd className="font-display mt-1 text-2xl font-semibold">{value ?? "–"}</dd>
            </div>
          ))}
        </dl>
      </section>
      {error && <ErrorState message={error} />}
      {!bookings && !error && <Skeleton className="h-48" />}
      {next && (
        <section className="mb-10">
          <h2 className="mb-3 text-base font-semibold text-ink-900">Next appointment</h2>
          <Link to={`/bookings/${next.reference}`} className="block rounded-2xl focus-visible:outline-2">
            <TokenStub booking={next} />
          </Link>
        </section>
      )}
      {bookings && bookings.length === 0 && (
        <section className="mb-10 rounded-2xl border border-dashed border-ink-300 bg-white px-6 py-8">
          <h2 className="text-lg font-semibold text-ink-900">No upcoming appointments</h2>
          <p className="mt-1 text-sm text-ink-500">When you book, your queue token and live position show up here.</p>
        </section>
      )}
      <section className="mb-10">
        <h2 className="mb-3 text-base font-semibold text-ink-900">Book something</h2>
        <div className="grid gap-3 sm:grid-cols-3">
          {PLACES.map(({ kind, line }) => {
            const meta = kindMeta[kind];
            const Icon = meta.icon;
            return (
              <Link key={kind} to={meta.path} className="surface group flex items-center gap-4 rounded-2xl px-5 py-5 transition-shadow hover:shadow-lg">
                <span className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-xl ${meta.tint}`}>
                  <Icon aria-hidden className={`h-6 w-6 ${meta.text}`} strokeWidth={1.75} />
                </span>
                <span>
                  <span className="font-display block text-lg font-semibold text-ink-900 group-hover:underline">{meta.plural}</span>
                  <span className="block text-sm text-ink-500">{line}</span>
                </span>
              </Link>
            );
          })}
        </div>
      </section>
      {bookings && bookings.length > 1 && (
        <section className="mb-10">
          <h2 className="mb-3 text-base font-semibold text-ink-900">Later appointments</h2>
          <ul className="divide-y divide-ink-100 overflow-hidden rounded-2xl border border-ink-100 bg-white">
            {bookings.slice(1, 5).map((b) => <BookingRow key={b.id} booking={b} />)}
          </ul>
        </section>
      )}
      {!!reservations?.length && (
        <section>
          <h2 className="mb-3 text-base font-semibold text-ink-900">Upcoming stays</h2>
          <ul className="divide-y divide-ink-100 overflow-hidden rounded-2xl border border-ink-100 bg-white">
            {reservations.slice(0, 4).map((r) => <ReservationRow key={r.id} reservation={r} />)}
          </ul>
        </section>
      )}
    </AppShell>
  );
}
