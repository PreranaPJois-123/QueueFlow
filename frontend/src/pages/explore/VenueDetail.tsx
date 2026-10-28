import { kindMeta } from "../../lib/kinds";
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ChevronLeft, MapPin } from "lucide-react";
import { VenueCover } from "../../components/VenueCover";
import { AppShell } from "../../components/AppShell";
import { EmptyState, ErrorState, Skeleton } from "../../components/States";
import { Panel, SampleTag } from "../../components/ui";
import { api, extractErrorMessage } from "../../lib/api";
import { money } from "../../lib/format";
import type { VenueDetail as Venue } from "../../types";
import HotelStay from "./HotelStay";

function policyLine(venue: Venue) {
  const hours = (m: number) => (m >= 60 ? `${Math.round(m / 60)} hour${m >= 120 ? "s" : ""}` : `${m} minutes`);
  return `Book up to ${venue.booking_horizon_days} days ahead, at least ${hours(venue.min_notice_minutes)} in advance. `
    + `Cancel or reschedule online until ${hours(venue.cancel_cutoff_minutes)} before your appointment.`;
}

export default function VenueDetail() {
  const { id } = useParams();
  const [venue, setVenue] = useState<Venue | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [spec, setSpec] = useState<string>("");

  useEffect(() => {
    setVenue(null);
    setError(null);
    api.get<Venue>(`/api/venues/${id}`).then((r) => setVenue(r.data)).catch((e) => setError(extractErrorMessage(e)));
  }, [id]);

  const offerings = useMemo(() => (venue?.offerings ?? []).filter((o) => !spec || o.specialization_id === spec), [venue, spec]);

  if (error) return <AppShell><ErrorState message={error} /></AppShell>;
  if (!venue) return <AppShell><Skeleton className="mb-4 h-24" /><Skeleton className="h-64" /></AppShell>;

  const meta = kindMeta[venue.kind];
  const providersFor = (offeringId: string) => venue.providers.filter((p) => p.offering_ids.includes(offeringId));
  const specName = (sid: string | null) => venue.specializations.find((s) => s.id === sid)?.name;

  return (
    <AppShell>
      <Link to={meta.path} className="mb-4 inline-flex items-center gap-1 text-sm font-medium text-ink-500 hover:text-ink-800">
        <ChevronLeft aria-hidden className="h-4 w-4" /> {meta.plural}
      </Link>
      <section className="surface mb-8 overflow-hidden rounded-3xl">
        <VenueCover name={venue.name} kind={venue.kind} className="h-40 md:h-52" large />
        <div className="flex flex-col gap-5 p-6 md:flex-row md:items-end md:justify-between md:p-8">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className={`rounded-md px-2 py-0.5 text-xs font-semibold ${meta.tint} ${meta.text}`}>{venue.category || meta.label}</span>
              {venue.is_sample && <SampleTag />}
            </div>
            <h1 className="mt-3 text-3xl font-semibold text-ink-900 md:text-4xl">{venue.name}</h1>
            <p className="mt-2 flex items-center gap-1.5 text-ink-500"><MapPin aria-hidden className="h-4 w-4" />{[venue.address, venue.city].filter(Boolean).join(", ")}</p>
          </div>
          <dl className="grid shrink-0 grid-cols-2 gap-3 text-sm sm:grid-cols-3">
            {(venue.kind === "HOTEL"
              ? [["Room types", venue.room_types.length], ["Check-in", venue.check_in_time?.slice(0, 5) ?? "14:00"], ["Free cancel", `${venue.free_cancellation_hours} h`]]
              : [["Services", venue.offerings.length], [venue.kind === "HOSPITAL" ? "Doctors" : "Team", venue.providers.length], ["Book ahead", `${venue.booking_horizon_days} days`]]
            ).map(([k, v]) => (
              <div key={String(k)} className="rounded-xl bg-paper px-4 py-3">
                <dt className="text-xs text-ink-500">{k}</dt>
                <dd className="font-display text-lg font-semibold text-ink-900">{v}</dd>
              </div>
            ))}
          </dl>
        </div>
      </section>
      {venue.is_sample && (
        <p className="mb-6 rounded-xl border border-dashed border-ink-300 bg-white px-4 py-3 text-sm text-ink-600">
          This is a sample listing for demonstration. Bookings here are not sent to a real {meta.label.toLowerCase()}.
        </p>
      )}
      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <div className="min-w-0 space-y-6">
          {venue.kind === "HOTEL" ? (
            <HotelStay venue={venue} />
          ) : (
            <Panel title={venue.kind === "HOSPITAL" ? "Consultations" : "Services"}>
              {venue.kind === "HOSPITAL" && venue.specializations.length > 1 && (
                <div className="mb-4 flex flex-wrap gap-2" role="group" aria-label="Filter by specialization">
                  {[{ id: "", name: "All" }, ...venue.specializations].map((s) => (
                    <button key={s.id} aria-pressed={spec === s.id} onClick={() => setSpec(s.id)}
                      className={`rounded-full border px-3 py-1 text-sm font-medium ${spec === s.id ? "border-care-600 bg-care-50 text-care-600" : "border-ink-200 text-ink-600"}`}>
                      {s.name}
                    </button>
                  ))}
                </div>
              )}
              {offerings.length === 0 ? (
                <EmptyState title="No bookable services yet" body="This venue hasn't published services online." />
              ) : (
                <ul className="divide-y divide-ink-100">
                  {offerings.map((o) => {
                    const people = providersFor(o.id);
                    return (
                      <li key={o.id} className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between">
                        <div className="min-w-0">
                          <p className="font-semibold text-ink-900">{o.name}</p>
                          <p className="mt-0.5 text-sm text-ink-500">
                            {[specName(o.specialization_id), `${o.duration_minutes} min`, o.price !== null ? money(o.price, venue.currency) : "Price at the venue"].filter(Boolean).join(", ")}
                          </p>
                          <p className="mt-1 text-sm text-ink-600">
                            {people.length ? `With ${people.map((p) => p.name).join(", ")}` : "No one is scheduled for this service yet"}
                          </p>
                        </div>
                        {people.length > 0 && (
                          <Link to={`/venues/${venue.id}/book?offering=${o.id}`} className="action-link shrink-0 justify-center">Choose a time</Link>
                        )}
                      </li>
                    );
                  })}
                </ul>
              )}
            </Panel>
          )}
        </div>
        <aside className="space-y-4">
          <Panel title="About">
            <p className="text-sm text-ink-600">{venue.description || "No description provided."}</p>
            {venue.phone && <p className="mt-3 text-sm text-ink-600">Phone: <a className="font-medium text-ink-900" href={`tel:${venue.phone}`}>{venue.phone}</a></p>}
          </Panel>
          <Panel title="Policies">
            <p className="text-sm text-ink-600">
              {venue.kind === "HOTEL"
                ? `Check-in from ${venue.check_in_time?.slice(0, 5) ?? "14:00"}, check-out by ${venue.check_out_time?.slice(0, 5) ?? "11:00"}. Free cancellation until ${venue.free_cancellation_hours} hours before check-in; later cancellations are charged one night. Taxes ${(Number(venue.tax_rate) * 100).toFixed(0)}%. Pay at the hotel.`
                : policyLine(venue)}
            </p>
            {venue.kind === "HOSPITAL" && (
              <p className="mt-3 text-sm text-ink-600">An appointment reserves a consultation time. In an emergency, call 112 or go to the nearest emergency department.</p>
            )}
          </Panel>
          {venue.kind !== "HOTEL" && venue.providers.length > 0 && (
            <Panel title={venue.kind === "HOSPITAL" ? "Doctors" : "Team"}>
              <ul className="space-y-3">
                {venue.providers.map((p) => (
                  <li key={p.id}>
                    <p className="text-sm font-medium text-ink-900">{p.name}</p>
                    <p className="text-xs text-ink-500">{p.title}</p>
                  </li>
                ))}
              </ul>
            </Panel>
          )}
        </aside>
      </div>
    </AppShell>
  );
}
