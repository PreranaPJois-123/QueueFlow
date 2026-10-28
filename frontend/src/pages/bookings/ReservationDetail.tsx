import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { AppShell } from "../../components/AppShell";
import { Button } from "../../components/Button";
import { ErrorState, Skeleton } from "../../components/States";
import { useToast } from "../../components/Toast";
import { Modal, PageHeader, Panel, StatusBadge, TextField } from "../../components/ui";
import { api, extractErrorMessage } from "../../lib/api";
import { addDays, calendarDate, dateTime, money, todayIn } from "../../lib/format";
import type { Reservation } from "../../types";
import { validateStay } from "../../lib/booking";

interface Terms {
  free_cancellation_until: string;
  late: boolean;
  fee: string;
  currency: string;
}

export default function ReservationDetail() {
  const { reference } = useParams();
  const [params] = useSearchParams();
  const { push } = useToast();
  const [reservation, setReservation] = useState<Reservation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [terms, setTerms] = useState<Terms | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const [modifyOpen, setModifyOpen] = useState(false);
  const [form, setForm] = useState({ checkIn: "", checkOut: "", guests: 1 });
  const [formErrors, setFormErrors] = useState<ReturnType<typeof validateStay>>({});
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get<Reservation>(`/api/reservations/${reference}`).then((r) => setReservation(r.data))
      .catch((e) => setError(extractErrorMessage(e)));
  }, [reference]);

  async function openCancel() {
    setBusy(true);
    try {
      const { data } = await api.get<Terms>(`/api/reservations/${reference}/cancellation-terms`);
      setTerms(data);
      setCancelling(true);
    } catch (e) {
      push(extractErrorMessage(e), "error");
    } finally {
      setBusy(false);
    }
  }

  async function cancel() {
    setBusy(true);
    try {
      const { data } = await api.post<Reservation>(`/api/reservations/${reference}/cancel`);
      setReservation(data);
      setCancelling(false);
      push("Reservation cancelled", "success");
    } catch (e) {
      push(extractErrorMessage(e), "error");
    } finally {
      setBusy(false);
    }
  }

  function openModify() {
    if (!reservation) return;
    setForm({ checkIn: reservation.check_in, checkOut: reservation.check_out, guests: reservation.guests });
    setFormErrors({});
    setSaveError(null);
    setModifyOpen(true);
  }

  async function save() {
    if (!reservation) return;
    const errors = validateStay(form.checkIn, form.checkOut, form.guests, todayIn(reservation.venue_timezone));
    setFormErrors(errors);
    if (Object.keys(errors).length) return;
    setSaving(true);
    setSaveError(null);
    try {
      const { data } = await api.post<Reservation>(`/api/reservations/${reference}/modify`,
        { check_in: form.checkIn, check_out: form.checkOut, guests: form.guests });
      setReservation(data);
      setModifyOpen(false);
      push(`Reservation updated. New total ${money(data.total, data.currency)}`, "success");
    } catch (e) {
      setSaveError(extractErrorMessage(e));
    } finally {
      setSaving(false);
    }
  }

  if (error) return <AppShell><ErrorState message={error} /><Link to="/bookings" className="action-link mt-4">Back to my bookings</Link></AppShell>;
  if (!reservation) return <AppShell><Skeleton className="h-64" /></AppShell>;
  const r = reservation;
  const editable = r.status === "CONFIRMED" && r.check_in > todayIn(r.venue_timezone);

  return (
    <AppShell>
      <PageHeader back={{ to: "/bookings", label: "My bookings" }} title={params.get("new") ? "Your room is reserved" : "Hotel reservation"}
        description={`${r.venue_name}, reference ${r.reference}`} />
      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <Panel>
          <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-xl font-semibold text-ink-900">{r.room_type_name}{r.rooms > 1 ? ` x ${r.rooms}` : ""}</h2>
            <StatusBadge status={r.status} />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="rounded-xl bg-stay-50 p-4">
              <p className="text-xs text-stay-600">Check-in</p>
              <p className="font-display text-lg font-semibold text-ink-900">{calendarDate(r.check_in)}</p>
              <p className="text-sm text-ink-600">from {r.check_in_time?.slice(0, 5) ?? "14:00"}</p>
            </div>
            <div className="rounded-xl bg-stay-50 p-4">
              <p className="text-xs text-stay-600">Check-out</p>
              <p className="font-display text-lg font-semibold text-ink-900">{calendarDate(r.check_out)}</p>
              <p className="text-sm text-ink-600">by {r.check_out_time?.slice(0, 5) ?? "11:00"}</p>
            </div>
          </div>
          <dl className="mt-5 space-y-2 text-sm">
            {[["Guests", String(r.guests)], ["Nightly rate", money(r.nightly_rate, r.currency)],
              ["Room charge", `${money(r.subtotal, r.currency)} for ${r.nights} night${r.nights > 1 ? "s" : ""}`],
              ["Taxes", money(r.taxes, r.currency)]].map(([k, v]) => (
              <div key={k} className="flex justify-between gap-4"><dt className="text-ink-500">{k}</dt><dd className="font-medium text-ink-800">{v}</dd></div>
            ))}
            <div className="flex justify-between gap-4 border-t border-ink-100 pt-2"><dt className="font-semibold text-ink-900">Total, payable at the hotel</dt>
              <dd className="font-display text-lg font-semibold text-ink-900">{money(r.total, r.currency)}</dd></div>
            {Number(r.cancellation_fee) > 0 && <div className="flex justify-between gap-4 text-rose-600"><dt>Late-cancellation charge</dt><dd>{money(r.cancellation_fee, r.currency)}</dd></div>}
          </dl>
          {r.special_requests && <p className="mt-4 text-sm text-ink-500">Requests: {r.special_requests}</p>}
        </Panel>
        <Panel title="Manage">
          {r.status === "CONFIRMED" ? (
            <>
              <p className="text-sm text-ink-600">Free cancellation until {dateTime(r.free_cancellation_until)}.</p>
              <div className="mt-4 flex flex-wrap gap-2">
                {editable && <Button variant="secondary" onClick={openModify}>Change dates</Button>}
                <Button variant="danger" onClick={() => void openCancel()} loading={busy && !cancelling}>Cancel reservation</Button>
              </div>
            </>
          ) : <p className="text-sm text-ink-500">This reservation can no longer be changed online.</p>}
          <Link to={`/venues/${r.venue_id}`} className="action-link mt-4">View hotel</Link>
        </Panel>
      </div>
      <Modal open={cancelling} title="Cancel this reservation?" onClose={() => setCancelling(false)}
        footer={<><Button variant="secondary" onClick={() => setCancelling(false)}>Keep reservation</Button>
          <Button variant="danger" loading={busy} onClick={() => void cancel()}>Cancel reservation</Button></>}>
        {terms && <p className="text-sm text-ink-600">{terms.late
          ? `The free-cancellation window ended ${dateTime(terms.free_cancellation_until)}. A charge of ${money(terms.fee, terms.currency)} will be payable to the hotel.`
          : "You're within the free-cancellation window, so no charge applies."}</p>}
      </Modal>
      <Modal open={modifyOpen} title="Change your stay" onClose={() => !saving && setModifyOpen(false)}
        footer={<><Button variant="secondary" onClick={() => setModifyOpen(false)} disabled={saving}>Back</Button>
          <Button loading={saving} onClick={() => void save()}>Save changes</Button></>}>
        <div className="space-y-4">
          <p className="text-sm text-ink-500">If the new dates aren't available your current reservation stays exactly as it is. The price is recalculated.</p>
          <TextField label="Check-in" type="date" value={form.checkIn} min={addDays(todayIn(r.venue_timezone), 1)} error={formErrors.checkIn}
            onChange={(e) => setForm((f) => ({ ...f, checkIn: e.target.value }))} />
          <TextField label="Check-out" type="date" value={form.checkOut} error={formErrors.checkOut}
            onChange={(e) => setForm((f) => ({ ...f, checkOut: e.target.value }))} />
          <TextField label="Guests" type="number" min={1} value={form.guests} error={formErrors.guests}
            onChange={(e) => setForm((f) => ({ ...f, guests: Number(e.target.value) }))} />
          {saveError && <ErrorState message={saveError} />}
        </div>
      </Modal>
    </AppShell>
  );
}
