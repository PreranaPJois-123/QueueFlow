import { kindMeta } from "../../lib/kinds";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { AppShell } from "../../components/AppShell";
import { Button } from "../../components/Button";
import { EmptyState, ErrorState, Skeleton } from "../../components/States";
import { useToast } from "../../components/Toast";
import { DataTable, Modal, PageHeader, SampleTag, SelectField, TextAreaField, TextField } from "../../components/ui";
import { api, extractErrorMessage, fieldErrors } from "../../lib/api";
import { emptyVenue, venuePayload, type VenueForm } from "../../lib/venueForm";
import type { VenueKind, VenueSummary } from "../../types";

export function VenueFields({ form, set, errors, lockKind }: {
  form: VenueForm; set: (patch: Partial<VenueForm>) => void; errors: Record<string, string>; lockKind?: boolean;
}) {
  const num = (k: keyof VenueForm) => (e: React.ChangeEvent<HTMLInputElement>) => set({ [k]: Number(e.target.value) } as Partial<VenueForm>);
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <SelectField label="Type" value={form.kind} disabled={lockKind} onChange={(e) => set({ kind: e.target.value as VenueKind })}>
        <option value="HOSPITAL">Hospital</option><option value="SHOP">Shop</option><option value="HOTEL">Hotel</option>
      </SelectField>
      <TextField label="Name" value={form.name} error={errors.name} onChange={(e) => set({ name: e.target.value })} />
      <TextField label="City" value={form.city} error={errors.city} onChange={(e) => set({ city: e.target.value })} />
      <TextField label="Address" value={form.address} onChange={(e) => set({ address: e.target.value })} />
      {form.kind === "SHOP" && <TextField label="Category" placeholder="Salon, Repair shop…" value={form.category} onChange={(e) => set({ category: e.target.value })} />}
      <TextField label="Phone" value={form.phone} onChange={(e) => set({ phone: e.target.value })} />
      <TextField label="Timezone" value={form.timezone} error={errors.timezone} hint="IANA name, e.g. Asia/Kolkata" onChange={(e) => set({ timezone: e.target.value })} />
      <div className="sm:col-span-2"><TextAreaField label="Description" value={form.description} onChange={(e) => set({ description: e.target.value })} /></div>
      {form.kind === "HOTEL" ? (
        <>
          <TextField label="Tax rate" hint="Fraction, e.g. 0.12 for 12%" value={form.tax_rate} error={errors.tax_rate} onChange={(e) => set({ tax_rate: e.target.value })} />
          <TextField label="Free cancellation (hours before check-in)" type="number" value={form.free_cancellation_hours} onChange={num("free_cancellation_hours")} />
          <TextField label="Check-in time" type="time" value={form.check_in_time} onChange={(e) => set({ check_in_time: e.target.value })} />
          <TextField label="Check-out time" type="time" value={form.check_out_time} onChange={(e) => set({ check_out_time: e.target.value })} />
        </>
      ) : (
        <>
          <TextField label="Booking window (days)" type="number" value={form.booking_horizon_days} error={errors.booking_horizon_days} onChange={num("booking_horizon_days")} />
          <TextField label="Minimum notice (minutes)" type="number" value={form.min_notice_minutes} onChange={num("min_notice_minutes")} />
          <TextField label="Cancellation cut-off (minutes)" type="number" value={form.cancel_cutoff_minutes} onChange={num("cancel_cutoff_minutes")} />
        </>
      )}
      <label className="flex items-center gap-2 text-sm text-ink-700 sm:col-span-2">
        <input type="checkbox" className="h-4 w-4 accent-ink-900" checked={form.is_active} onChange={(e) => set({ is_active: e.target.checked })} />
        Visible to customers
      </label>
    </div>
  );
}

export default function AdminVenues() {
  const navigate = useNavigate();
  const { push } = useToast();
  const [venues, setVenues] = useState<VenueSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<VenueForm>(emptyVenue);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  const load = useCallback(() => {
    api.get<VenueSummary[]>("/api/admin/venues").then((r) => setVenues(r.data)).catch((e) => setError(extractErrorMessage(e)));
  }, []);
  useEffect(load, [load]);

  async function create(e?: FormEvent) {
    e?.preventDefault();
    const local: Record<string, string> = {};
    if (form.name.trim().length < 2) local.name = "Enter a name";
    if (form.city.trim().length < 2) local.city = "Enter a city";
    setErrors(local);
    if (Object.keys(local).length) return;
    setSaving(true);
    try {
      const { data } = await api.post<VenueSummary>("/api/admin/venues", venuePayload(form));
      push("Venue created", "success");
      navigate(`/admin/venues/${data.id}`);
    } catch (failure) {
      const fe = fieldErrors(failure);
      setErrors(fe);
      if (!Object.keys(fe).length) push(extractErrorMessage(failure), "error");
    } finally {
      setSaving(false);
    }
  }

  return (
    <AppShell>
      <PageHeader title="Venues" description="Hospitals, shops and hotels, including hidden ones."
        actions={<Button onClick={() => { setForm(emptyVenue); setErrors({}); setOpen(true); }}>Add venue</Button>} />
      {error && <ErrorState message={error} />}
      {!venues && !error && <Skeleton className="h-48" />}
      {venues && (
        <DataTable rows={venues} rowKey={(v) => v.id}
          empty={<EmptyState title="No venues yet" body="Add one, or run `python -m app.seed` to load sample data." />}
          columns={[
            { header: "Name", cell: (v) => <Link to={`/admin/venues/${v.id}`} className="flex items-center gap-2 font-semibold text-ink-900 hover:underline">{v.name}{v.is_sample && <SampleTag />}</Link> },
            { header: "Type", cell: (v) => kindMeta[v.kind].label },
            { header: "City", cell: (v) => v.city },
            { header: "Visibility", cell: (v) => v.is_active ? <span className="text-signal-700">Visible</span> : <span className="text-ink-400">Hidden</span> },
          ]} />
      )}
      <Modal open={open} wide title="Add venue" onClose={() => !saving && setOpen(false)}
        footer={<><Button variant="secondary" onClick={() => setOpen(false)}>Cancel</Button><Button loading={saving} onClick={() => void create()}>Create venue</Button></>}>
        <form onSubmit={create}><VenueFields form={form} set={(p) => setForm((f) => ({ ...f, ...p }))} errors={errors} /></form>
      </Modal>
    </AppShell>
  );
}
