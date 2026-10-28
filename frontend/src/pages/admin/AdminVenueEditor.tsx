import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { AppShell } from "../../components/AppShell";
import { Button } from "../../components/Button";
import { EmptyState, ErrorState, Skeleton } from "../../components/States";
import { useToast } from "../../components/Toast";
import { DataTable, Modal, PageHeader, Panel, SelectField, Tabs, TextAreaField, TextField } from "../../components/ui";
import { api, extractErrorMessage, fieldErrors } from "../../lib/api";
import { money } from "../../lib/format";
import type { Offering, RoomType, Specialization, User, VenueDetail } from "../../types";
import { VenueFields } from "./AdminVenues";
import { venuePayload, venueToForm, type VenueForm } from "../../lib/venueForm";

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
type Tab = "details" | "services" | "people" | "rooms" | "staff";

interface AdminProvider {
  id: string; name: string; title: string; bio: string; specialization_id: string | null; token_prefix: string;
  is_active: boolean; offering_ids: string[]; schedules: { weekday: number; start_time: string; end_time: string }[];
}

function useSave() {
  const { push } = useToast();
  const [saving, setSaving] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const save = async (fn: () => Promise<unknown>, ok: string) => {
    setSaving(true);
    setErrors({});
    try {
      await fn();
      push(ok, "success");
      return true;
    } catch (e) {
      const fe = fieldErrors(e);
      setErrors(fe);
      push(Object.keys(fe).length ? "Check the highlighted fields" : extractErrorMessage(e), "error");
      return false;
    } finally {
      setSaving(false);
    }
  };
  return { saving, errors, save };
}

function Details({ venue, reload }: { venue: VenueDetail; reload: () => void }) {
  const [form, setForm] = useState<VenueForm>(venueToForm(venue));
  const { saving, errors, save } = useSave();
  return (
    <Panel>
      <VenueFields form={form} set={(p) => setForm((f) => ({ ...f, ...p }))} errors={errors} lockKind />
      <Button className="mt-6" loading={saving} onClick={() => void save(() => api.put(`/api/admin/venues/${venue.id}`, venuePayload(form)), "Venue saved").then((ok) => ok && reload())}>Save details</Button>
    </Panel>
  );
}

function Services({ venue, specs, reload }: { venue: VenueDetail; specs: Specialization[]; reload: () => void }) {
  const blank = { name: "", description: "", duration_minutes: 15, price: "", specialization_id: "", is_active: true };
  const [editing, setEditing] = useState<(typeof blank & { id?: string }) | null>(null);
  const { saving, errors, save } = useSave();
  const submit = async () => {
    if (!editing) return;
    const body = { ...editing, price: editing.price === "" ? null : editing.price, specialization_id: editing.specialization_id || null };
    delete (body as { id?: string }).id;
    const ok = await save(() => editing.id ? api.put(`/api/admin/offerings/${editing.id}`, body) : api.post(`/api/admin/venues/${venue.id}/offerings`, body), "Service saved");
    if (ok) { setEditing(null); reload(); }
  };
  const edit = (o: Offering) => setEditing({ id: o.id, name: o.name, description: o.description, duration_minutes: o.duration_minutes,
    price: o.price ?? "", specialization_id: o.specialization_id ?? "", is_active: o.is_active });
  return (
    <>
      <div className="mb-4 flex justify-end"><Button onClick={() => setEditing(blank)}>Add service</Button></div>
      <DataTable rows={venue.offerings} rowKey={(o) => o.id} empty={<EmptyState title="No services yet" body="Add the first bookable service." />}
        columns={[
          { header: "Service", cell: (o) => <><p className="font-medium">{o.name}</p>{o.specialization_id && <p className="text-xs text-ink-500">{specs.find((s) => s.id === o.specialization_id)?.name}</p>}</> },
          { header: "Duration", cell: (o) => `${o.duration_minutes} min` },
          { header: "Price", cell: (o) => (o.price !== null ? money(o.price, venue.currency) : "At venue") },
          { header: "Status", cell: (o) => (o.is_active ? "Active" : <span className="text-ink-400">Hidden</span>) },
          { header: "", cell: (o) => <Button size="sm" variant="ghost" onClick={() => edit(o)}>Edit</Button> },
        ]} />
      <Modal open={!!editing} title={editing?.id ? "Edit service" : "Add service"} onClose={() => setEditing(null)}
        footer={<><Button variant="secondary" onClick={() => setEditing(null)}>Cancel</Button><Button loading={saving} onClick={() => void submit()}>Save service</Button></>}>
        {editing && (
          <div className="space-y-4">
            <TextField label="Name" value={editing.name} error={errors.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })} />
            {venue.kind === "HOSPITAL" && (
              <SelectField label="Specialization" value={editing.specialization_id} onChange={(e) => setEditing({ ...editing, specialization_id: e.target.value })}>
                <option value="">None</option>{specs.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </SelectField>
            )}
            <div className="grid grid-cols-2 gap-4">
              <TextField label="Duration (minutes)" type="number" value={editing.duration_minutes} error={errors.duration_minutes} onChange={(e) => setEditing({ ...editing, duration_minutes: Number(e.target.value) })} />
              <TextField label={`Price (${venue.currency})`} hint="Leave empty if set at the venue" value={editing.price} error={errors.price} onChange={(e) => setEditing({ ...editing, price: e.target.value })} />
            </div>
            <TextAreaField label="Description" value={editing.description} onChange={(e) => setEditing({ ...editing, description: e.target.value })} />
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="accent-ink-900" checked={editing.is_active} onChange={(e) => setEditing({ ...editing, is_active: e.target.checked })} />Bookable</label>
          </div>
        )}
      </Modal>
    </>
  );
}

function People({ venue, specs }: { venue: VenueDetail; specs: Specialization[] }) {
  const [providers, setProviders] = useState<AdminProvider[] | null>(null);
  const [editing, setEditing] = useState<(Omit<AdminProvider, "id"> & { id?: string }) | null>(null);
  const { saving, errors, save } = useSave();
  const load = useCallback(() => { api.get<AdminProvider[]>(`/api/admin/venues/${venue.id}/providers`).then((r) => setProviders(r.data)); }, [venue.id]);
  useEffect(load, [load]);
  const blank = { name: "", title: "", bio: "", specialization_id: null, token_prefix: "", is_active: true, offering_ids: [],
    schedules: [0, 1, 2, 3, 4].map((d) => ({ weekday: d, start_time: "09:00", end_time: "13:00" })) };
  const submit = async () => {
    if (!editing) return;
    const { id, ...body } = editing;
    const ok = await save(() => id ? api.put(`/api/admin/providers/${id}`, body) : api.post(`/api/admin/venues/${venue.id}/providers`, body), "Saved");
    if (ok) { setEditing(null); load(); }
  };
  const label = venue.kind === "HOSPITAL" ? "doctor" : "staff member";
  if (!providers) return <Skeleton className="h-40" />;
  return (
    <>
      <div className="mb-4 flex justify-end"><Button onClick={() => setEditing(blank)}>Add {label}</Button></div>
      <DataTable rows={providers} rowKey={(p) => p.id} empty={<EmptyState title={`No ${label}s yet`} body="Appointments need at least one provider with a schedule." />}
        columns={[
          { header: "Name", cell: (p) => <><p className="font-medium">{p.name}</p><p className="text-xs text-ink-500">{p.title}</p></> },
          { header: "Token prefix", cell: (p) => <span className="font-display font-semibold">{p.token_prefix}</span> },
          { header: "Services", cell: (p) => p.offering_ids.map((id) => venue.offerings.find((o) => o.id === id)?.name).filter(Boolean).join(", ") || <span className="text-rose-600">None</span> },
          { header: "Hours", cell: (p) => `${p.schedules.length} window${p.schedules.length === 1 ? "" : "s"}/week` },
          { header: "", cell: (p) => <Button size="sm" variant="ghost" onClick={() => setEditing(p)}>Edit</Button> },
        ]} />
      <Modal open={!!editing} wide title={editing?.id ? `Edit ${label}` : `Add ${label}`} onClose={() => setEditing(null)}
        footer={<><Button variant="secondary" onClick={() => setEditing(null)}>Cancel</Button><Button loading={saving} onClick={() => void submit()}>Save</Button></>}>
        {editing && (
          <div className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <TextField label="Name" value={editing.name} error={errors.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })} />
              <TextField label="Title" value={editing.title} onChange={(e) => setEditing({ ...editing, title: e.target.value })} />
              <TextField label="Token prefix" hint="Capital letters/digits, e.g. CAR1" value={editing.token_prefix} error={errors.token_prefix}
                onChange={(e) => setEditing({ ...editing, token_prefix: e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 8) })} />
              {venue.kind === "HOSPITAL" && (
                <SelectField label="Specialization" value={editing.specialization_id ?? ""} onChange={(e) => setEditing({ ...editing, specialization_id: e.target.value || null })}>
                  <option value="">None</option>{specs.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                </SelectField>
              )}
            </div>
            <fieldset>
              <legend className="label mb-2">Services this {label} provides</legend>
              <div className="flex flex-wrap gap-2">
                {venue.offerings.map((o) => {
                  const on = editing.offering_ids.includes(o.id);
                  return <button type="button" key={o.id} aria-pressed={on} onClick={() => setEditing({ ...editing, offering_ids: on ? editing.offering_ids.filter((x) => x !== o.id) : [...editing.offering_ids, o.id] })}
                    className={`rounded-full border px-3 py-1 text-sm ${on ? "border-ink-900 bg-ink-900 text-white" : "border-ink-200 text-ink-600"}`}>{o.name}</button>;
                })}
              </div>
            </fieldset>
            <fieldset>
              <legend className="label mb-2">Weekly hours ({venue.timezone})</legend>
              <div className="space-y-2">
                {editing.schedules.map((s, i) => (
                  <div key={i} className="flex flex-wrap items-center gap-2">
                    <select aria-label="Day" className="field w-24" value={s.weekday} onChange={(e) => setEditing({ ...editing, schedules: editing.schedules.map((x, j) => j === i ? { ...x, weekday: Number(e.target.value) } : x) })}>
                      {WEEKDAYS.map((d, n) => <option key={d} value={n}>{d}</option>)}
                    </select>
                    <input aria-label="Opens" type="time" className="field w-32" value={s.start_time.slice(0, 5)} onChange={(e) => setEditing({ ...editing, schedules: editing.schedules.map((x, j) => j === i ? { ...x, start_time: e.target.value } : x) })} />
                    <span className="text-sm text-ink-400">to</span>
                    <input aria-label="Closes" type="time" className="field w-32" value={s.end_time.slice(0, 5)} onChange={(e) => setEditing({ ...editing, schedules: editing.schedules.map((x, j) => j === i ? { ...x, end_time: e.target.value } : x) })} />
                    <Button size="sm" variant="ghost" onClick={() => setEditing({ ...editing, schedules: editing.schedules.filter((_, j) => j !== i) })}>Remove</Button>
                  </div>
                ))}
                <Button size="sm" variant="secondary" onClick={() => setEditing({ ...editing, schedules: [...editing.schedules, { weekday: 0, start_time: "14:00", end_time: "17:00" }] })}>Add hours</Button>
              </div>
            </fieldset>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="accent-ink-900" checked={editing.is_active} onChange={(e) => setEditing({ ...editing, is_active: e.target.checked })} />Taking bookings</label>
          </div>
        )}
      </Modal>
    </>
  );
}

function Rooms({ venue, reload }: { venue: VenueDetail; reload: () => void }) {
  const blank = { name: "", description: "", amenities: "", max_occupancy: 2, nightly_rate: "", total_rooms: 1, is_active: true };
  const [editing, setEditing] = useState<(typeof blank & { id?: string }) | null>(null);
  const { saving, errors, save } = useSave();
  const submit = async () => {
    if (!editing) return;
    const { id, ...body } = editing;
    const ok = await save(() => id ? api.put(`/api/admin/room-types/${id}`, body) : api.post(`/api/admin/venues/${venue.id}/room-types`, body), "Room type saved");
    if (ok) { setEditing(null); reload(); }
  };
  return (
    <>
      <div className="mb-4 flex justify-end"><Button onClick={() => setEditing(blank)}>Add room type</Button></div>
      <DataTable rows={venue.room_types} rowKey={(r) => r.id} empty={<EmptyState title="No room types yet" body="Add room types with nightly rates and inventory." />}
        columns={[
          { header: "Room type", cell: (r) => <><p className="font-medium">{r.name}</p><p className="text-xs text-ink-500">Sleeps {r.max_occupancy}</p></> },
          { header: "Nightly rate", cell: (r) => money(r.nightly_rate, venue.currency) },
          { header: "Rooms", cell: (r) => r.total_rooms },
          { header: "Status", cell: (r) => (r.is_active ? "Bookable" : <span className="text-ink-400">Hidden</span>) },
          { header: "", cell: (r: RoomType) => <Button size="sm" variant="ghost" onClick={() => setEditing({ ...r })}>Edit</Button> },
        ]} />
      <Modal open={!!editing} title={editing?.id ? "Edit room type" : "Add room type"} onClose={() => setEditing(null)}
        footer={<><Button variant="secondary" onClick={() => setEditing(null)}>Cancel</Button><Button loading={saving} onClick={() => void submit()}>Save room type</Button></>}>
        {editing && (
          <div className="space-y-4">
            <TextField label="Name" value={editing.name} error={errors.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })} />
            <div className="grid grid-cols-3 gap-3">
              <TextField label={`Rate (${venue.currency})`} value={editing.nightly_rate} error={errors.nightly_rate} onChange={(e) => setEditing({ ...editing, nightly_rate: e.target.value })} />
              <TextField label="Sleeps" type="number" value={editing.max_occupancy} onChange={(e) => setEditing({ ...editing, max_occupancy: Number(e.target.value) })} />
              <TextField label="Rooms" type="number" value={editing.total_rooms} onChange={(e) => setEditing({ ...editing, total_rooms: Number(e.target.value) })} />
            </div>
            <TextField label="Amenities" value={editing.amenities} onChange={(e) => setEditing({ ...editing, amenities: e.target.value })} />
            <TextAreaField label="Description" value={editing.description} onChange={(e) => setEditing({ ...editing, description: e.target.value })} />
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="accent-ink-900" checked={editing.is_active} onChange={(e) => setEditing({ ...editing, is_active: e.target.checked })} />Bookable</label>
          </div>
        )}
      </Modal>
    </>
  );
}

function Staff({ venue }: { venue: VenueDetail }) {
  const { push } = useToast();
  const [assigned, setAssigned] = useState<User[] | null>(null);
  const [candidates, setCandidates] = useState<User[]>([]);
  const [choice, setChoice] = useState("");
  const load = useCallback(() => {
    api.get<User[]>(`/api/admin/venues/${venue.id}/staff`).then((r) => setAssigned(r.data));
    api.get<User[]>("/api/admin/users", { params: { role: "STAFF" } }).then((r) => setCandidates(r.data));
  }, [venue.id]);
  useEffect(load, [load]);
  const act = async (fn: () => Promise<unknown>, ok: string) => {
    try { await fn(); push(ok, "success"); load(); } catch (e) { push(extractErrorMessage(e), "error"); }
  };
  const available = candidates.filter((c) => !assigned?.some((a) => a.id === c.id));
  return (
    <Panel>
      <p className="mb-4 text-sm text-ink-500">Assigned staff can run this venue's queues and front desk. Give someone the Staff role under People first.</p>
      <div className="mb-6 flex flex-wrap gap-2">
        <label htmlFor="staff-choice" className="sr-only">Staff member</label>
        <select id="staff-choice" className="field w-auto min-w-64" value={choice} onChange={(e) => setChoice(e.target.value)}>
          <option value="">Choose a staff account</option>
          {available.map((u) => <option key={u.id} value={u.id}>{u.full_name} ({u.email})</option>)}
        </select>
        <Button disabled={!choice} onClick={() => void act(() => api.post(`/api/admin/venues/${venue.id}/staff`, { user_id: choice }), "Staff assigned").then(() => setChoice(""))}>Assign</Button>
      </div>
      {!assigned ? <Skeleton className="h-20" /> : assigned.length === 0 ? <p className="text-sm text-ink-400">Nobody is assigned yet.</p> : (
        <ul className="divide-y divide-ink-100">
          {assigned.map((u) => (
            <li key={u.id} className="flex items-center justify-between py-3">
              <div><p className="text-sm font-medium text-ink-900">{u.full_name}</p><p className="text-xs text-ink-500">{u.email}</p></div>
              <Button size="sm" variant="ghost" onClick={() => void act(() => api.delete(`/api/admin/venues/${venue.id}/staff/${u.id}`), "Removed from venue")}>Remove</Button>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

export default function AdminVenueEditor() {
  const { id } = useParams();
  const [venue, setVenue] = useState<VenueDetail | null>(null);
  const [specs, setSpecs] = useState<Specialization[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("details");
  const load = useCallback(() => {
    api.get<VenueDetail>(`/api/admin/venues/${id}`).then((r) => setVenue(r.data)).catch((e) => setError(extractErrorMessage(e)));
  }, [id]);
  useEffect(() => {
    load();
    api.get<Specialization[]>("/api/admin/specializations").then((r) => setSpecs(r.data)).catch(() => setSpecs([]));
  }, [load]);
  if (error) return <AppShell><ErrorState message={error} /></AppShell>;
  if (!venue) return <AppShell><Skeleton className="h-64" /></AppShell>;
  const tabs: { value: Tab; label: string }[] = venue.kind === "HOTEL"
    ? [{ value: "details", label: "Details" }, { value: "rooms", label: "Room types" }, { value: "staff", label: "Staff" }]
    : [{ value: "details", label: "Details" }, { value: "services", label: "Services" },
       { value: "people", label: venue.kind === "HOSPITAL" ? "Doctors" : "Team" }, { value: "staff", label: "Staff access" }];
  return (
    <AppShell>
      <PageHeader back={{ to: "/admin/venues", label: "Venues" }} title={venue.name} description={`${venue.city}. Changes are re-indexed for Wayzen automatically.`} />
      <Tabs label="Venue sections" value={tab} onChange={setTab} items={tabs} />
      {tab === "details" && <Details key={venue.id} venue={venue} reload={load} />}
      {tab === "services" && <Services venue={venue} specs={specs} reload={load} />}
      {tab === "people" && <People venue={venue} specs={specs} />}
      {tab === "rooms" && <Rooms venue={venue} reload={load} />}
      {tab === "staff" && <Staff venue={venue} />}
    </AppShell>
  );
}
