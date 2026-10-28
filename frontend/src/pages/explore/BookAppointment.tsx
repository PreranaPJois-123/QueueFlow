import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { AppShell } from "../../components/AppShell";
import { Button } from "../../components/Button";
import { EmptyState, ErrorState, Skeleton } from "../../components/States";
import { PageHeader, Panel, SampleTag, TextAreaField } from "../../components/ui";
import { api, extractErrorMessage, newIdempotencyKey } from "../../lib/api";
import { addDays, calendarDate, money, todayIn, venueDate, venueTime } from "../../lib/format";
import { groupSlots } from "../../lib/booking";
import type { Booking, Slot, VenueDetail } from "../../types";

function Step({ n, title, children, done }: { n: number; title: string; children: React.ReactNode; done?: boolean }) {
  return (
    <Panel>
      <div className="mb-4 flex items-center gap-3">
        <span className={`font-display flex h-7 w-7 items-center justify-center rounded-full text-sm font-semibold ${done ? "bg-ink-900 text-white" : "bg-ink-100 text-ink-600"}`}>{n}</span>
        <h2 className="text-base font-semibold text-ink-900">{title}</h2>
      </div>
      {children}
    </Panel>
  );
}

export default function BookAppointment() {
  const { id } = useParams();
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const [venue, setVenue] = useState<VenueDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const offeringId = params.get("offering") || "";
  const providerId = params.get("provider") || "";
  const [day, setDay] = useState<string>("");
  const [slots, setSlots] = useState<Slot[] | null>(null);
  const [slotError, setSlotError] = useState<string | null>(null);
  const [slot, setSlot] = useState<Slot | null>(null);
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  const idempotency = useMemo(() => newIdempotencyKey(), [slot?.start_at, slot?.provider_id]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    api.get<VenueDetail>(`/api/venues/${id}`).then((r) => {
      setVenue(r.data);
      setDay(todayIn(r.data.timezone));
    }).catch((e) => setError(extractErrorMessage(e)));
  }, [id]);

  useEffect(() => {
    if (!venue || !offeringId || !day) return;
    const controller = new AbortController();
    setSlots(null);
    setSlotError(null);
    api.get<Slot[]>(`/api/venues/${venue.id}/slots`, { signal: controller.signal,
      params: { offering_id: offeringId, date: day, provider_id: providerId || undefined } })
      .then((r) => setSlots(r.data))
      .catch((e) => !controller.signal.aborted && setSlotError(extractErrorMessage(e)));
    return () => controller.abort();
  }, [venue, offeringId, providerId, day, reload]);

  if (error) return <AppShell><ErrorState message={error} /></AppShell>;
  if (!venue) return <AppShell><Skeleton className="h-96" /></AppShell>;

  const offering = venue.offerings.find((o) => o.id === offeringId);
  const providers = venue.providers.filter((p) => offering && p.offering_ids.includes(offering.id));
  const today = todayIn(venue.timezone);
  const days = Array.from({ length: Math.min(14, venue.booking_horizon_days + 1) }, (_, i) => addDays(today, i));
  const isHospital = venue.kind === "HOSPITAL";
  const who = isHospital ? "doctor" : "staff member";

  const update = (key: string, value: string) => {
    setParams((p) => { if (value) p.set(key, value); else p.delete(key); if (key === "offering") p.delete("provider"); return p; }, { replace: true });
    setSlot(null);
  };

  async function confirm() {
    if (!slot || !offering) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const { data } = await api.post<Booking>("/api/bookings", {
        venue_id: venue!.id, offering_id: offering.id, provider_id: slot.provider_id, start_at: slot.start_at,
        notes: notes.trim() || null,
      }, { headers: { "Idempotency-Key": idempotency } });
      navigate(`/bookings/${data.reference}?new=1`);
    } catch (failure) {
      setSubmitError(extractErrorMessage(failure));
      setSlot(null);
      setReload((r) => r + 1);
    } finally {
      setSubmitting(false);
    }
  }

  const grouped = slots ? groupSlots(slots, venue.timezone) : null;

  return (
    <AppShell>
      <PageHeader back={{ to: `/venues/${venue.id}`, label: venue.name }} title="Book an appointment"
        description={<span className="flex flex-wrap items-center gap-2">{venue.name}, {venue.city}{venue.is_sample && <SampleTag />}</span>} />
      <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
        <div className="min-w-0 space-y-5">
          <Step n={1} title={isHospital ? "Consultation" : "Service"} done={!!offering}>
            <div className="grid gap-2 sm:grid-cols-2">
              {venue.offerings.filter((o) => venue.providers.some((p) => p.offering_ids.includes(o.id))).map((o) => (
                <button key={o.id} onClick={() => update("offering", o.id)} aria-pressed={o.id === offeringId}
                  className={`rounded-xl border px-4 py-3 text-left transition-colors ${o.id === offeringId ? "border-ink-900 bg-ink-900 text-white" : "border-ink-200 hover:border-ink-400"}`}>
                  <span className="block text-sm font-semibold">{o.name}</span>
                  <span className={`block text-xs ${o.id === offeringId ? "text-ink-200" : "text-ink-500"}`}>
                    {o.duration_minutes} min{o.price !== null ? `, ${money(o.price, venue.currency)}` : ""}
                  </span>
                </button>
              ))}
            </div>
          </Step>
          {offering && (
            <Step n={2} title={`Choose a ${who}`} done>
              <div className="flex flex-wrap gap-2">
                {[{ id: "", name: `Any available ${who}`, title: "" }, ...providers].map((p) => (
                  <button key={p.id} onClick={() => update("provider", p.id)} aria-pressed={providerId === p.id}
                    className={`rounded-xl border px-4 py-2.5 text-left text-sm ${providerId === p.id ? "border-ink-900 bg-ink-50 font-semibold text-ink-900" : "border-ink-200 text-ink-700 hover:border-ink-400"}`}>
                    {p.name}{p.title && <span className="block text-xs font-normal text-ink-500">{p.title}</span>}
                  </button>
                ))}
              </div>
            </Step>
          )}
          {offering && (
            <Step n={3} title="Date and time" done={!!slot}>
              <div className="-mx-1 mb-4 flex gap-2 overflow-x-auto px-1 pb-1" role="group" aria-label="Choose a date">
                {days.map((d) => (
                  <button key={d} onClick={() => { setDay(d); setSlot(null); }} aria-pressed={d === day}
                    className={`shrink-0 rounded-xl border px-3 py-2 text-center ${d === day ? "border-ink-900 bg-ink-900 text-white" : "border-ink-200 bg-white text-ink-700 hover:border-ink-400"}`}>
                    <span className="block text-xs">{calendarDate(d, { weekday: "short", day: undefined, month: undefined, year: undefined })}</span>
                    <span className="font-display block text-lg font-semibold">{Number(d.slice(8))}</span>
                  </button>
                ))}
              </div>
              {slotError && <ErrorState message={slotError} />}
              {!slots && !slotError && <Skeleton className="h-24" />}
              {slots && slots.length === 0 && (
                <EmptyState title={`No free times on ${calendarDate(day)}`} body="Pick another date, or choose a different provider." />
              )}
              {grouped && slots && slots.length > 0 && (
                <div className="space-y-4">
                  {Object.entries(grouped).filter(([, list]) => list.length).map(([label, list]) => (
                    <div key={label}>
                      <p className="mb-2 text-xs font-medium text-ink-500">{label}</p>
                      <div className="flex flex-wrap gap-2">
                        {list.map((s) => {
                          const active = slot?.start_at === s.start_at && slot.provider_id === s.provider_id;
                          return (
                            <button key={s.start_at + s.provider_id} onClick={() => setSlot(s)} aria-pressed={active}
                              title={s.provider_name}
                              className={`rounded-lg border px-3 py-2 text-sm font-medium tabular-nums ${active ? "border-ink-900 bg-ink-900 text-white" : "border-ink-200 bg-white text-ink-800 hover:border-ink-500"}`}>
                              {venueTime(s.start_at, venue.timezone)}
                              {!providerId && providers.length > 1 && <span className={`ml-1.5 text-xs ${active ? "text-ink-200" : "text-ink-400"}`}>{s.provider_name.replace(/^Dr\. /, "Dr ").split(" ").slice(0, 2).join(" ")}</span>}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Step>
          )}
        </div>
        <aside className="lg:sticky lg:top-20 lg:self-start">
          <Panel title="Review">
            {!slot || !offering ? (
              <p className="text-sm text-ink-500">Choose a service, {who} and time to review your booking.</p>
            ) : (
              <div className="space-y-4 text-sm">
                <dl className="space-y-2">
                  {[["Service", offering.name], [isHospital ? "Doctor" : "With", slot.provider_name],
                    ["Date", venueDate(slot.start_at, venue.timezone)], ["Time", `${venueTime(slot.start_at, venue.timezone)} to ${venueTime(slot.end_at, venue.timezone)}`],
                    ["Fee", offering.price !== null ? `${money(offering.price, venue.currency)}, paid at the venue` : "Paid at the venue"]].map(([k, v]) => (
                    <div key={k} className="flex justify-between gap-3"><dt className="text-ink-500">{k}</dt><dd className="text-right font-medium text-ink-800">{v}</dd></div>
                  ))}
                </dl>
                <TextAreaField label="Note for the front desk (optional)" maxLength={500} value={notes}
                  onChange={(e) => setNotes(e.target.value)} hint={isHospital ? "Don't include medical details you wouldn't share at reception." : undefined} />
                <p className="text-xs text-ink-500">
                  You'll get a booking reference and queue token. You can cancel or reschedule until {venue.cancel_cutoff_minutes >= 60 ? `${Math.round(venue.cancel_cutoff_minutes / 60)} h` : `${venue.cancel_cutoff_minutes} min`} before.
                </p>
                {submitError && <ErrorState message={submitError} />}
                <Button className="w-full" onClick={() => void confirm()} loading={submitting}>Confirm booking</Button>
              </div>
            )}
          </Panel>
        </aside>
      </div>
    </AppShell>
  );
}
