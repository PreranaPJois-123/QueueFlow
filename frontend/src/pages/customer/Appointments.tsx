import { useClock } from "../../lib/useClock";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { AppShell } from "../../components/AppShell";
import { Button } from "../../components/Button";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { EmptyState } from "../../components/States";
import { Heading, Card, ResourceState } from "../../components/Product";
import { dateTime } from "../../lib/format";
import { useResource } from "../../lib/useResource";
import { api, extractErrorMessage } from "../../lib/api";
import { useToast } from "../../components/Toast";
import type { Service, CustomerData } from "../../types";
export default function Appointments() {
  const now = useClock();
  const [params] = useSearchParams();
  const mine = useResource<CustomerData>("/api/product/mine");
  const services = useResource<Service[]>("/api/services");
  const [serviceId, setServiceId] = useState(params.get("service") ?? "");
  const [day, setDay] = useState("");
  const [time, setTime] = useState("");
  const [notes, setNotes] = useState("");
  const [pending, setPending] = useState(false);
  const [cancel, setCancel] = useState<string | null>(null);
  const [filter, setFilter] = useState("upcoming");
  const chosen = serviceId || services.data?.[0]?.id || "";
  const offset = day ? -new Date(`${day}T12:00:00`).getTimezoneOffset() : 0;
  const availability = useResource<{
    slots: string[];
    duration_minutes: number;
  }>(
    chosen && day
      ? `/api/appointments/availability/${chosen}?day=${day}&utc_offset_minutes=${offset}`
      : null,
    15000,
  );
  const { push } = useToast();
  async function book(e: React.FormEvent) {
    e.preventDefault();
    setPending(true);
    try {
      if (!time || new Date(time).getTime() <= now)
        throw new Error("Choose a future available time");
      await api.post("/api/appointments", {
        service_id: chosen,
        scheduled_time: time,
        notes: notes || undefined,
      });
      push("Appointment confirmed", "success");
      setTime("");
      setNotes("");
      mine.refresh();
      availability.refresh();
    } catch (e) {
      push(
        e instanceof Error && !("response" in e)
          ? e.message
          : extractErrorMessage(e),
        "error",
      );
      availability.refresh();
    } finally {
      setPending(false);
    }
  }
  async function cancelBooking() {
    try {
      await api.post(`/api/appointments/${cancel}/cancel`);
      push("Appointment cancelled", "success");
      setCancel(null);
      mine.refresh();
      availability.refresh();
    } catch (e) {
      push(extractErrorMessage(e), "error");
    }
  }
  const rows =
    mine.data?.appointments.filter(
      (a) =>
        filter === "all" ||
        (filter === "upcoming"
          ? ["SCHEDULED", "CHECKED_IN"].includes(a.status) &&
            new Date(a.scheduled_time).getTime() >= now
          : !["SCHEDULED", "CHECKED_IN"].includes(a.status) ||
            new Date(a.scheduled_time).getTime() < now),
    ) ?? [];
  const today = new Date();
  const dateMin = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
  return (
    <AppShell variant="customer">
      <Heading
        title="Appointments"
        body="Plan a visit. Available times reflect real service bookings."
      />
      <ResourceState {...mine} />
      <ResourceState {...services} />
      <div className="mt-6 grid gap-6 lg:grid-cols-[360px_1fr]">
        <Card title="Book your visit">
          {services.data?.length ? (
            <form onSubmit={book} className="space-y-4">
              <label className="label">
                Service
                <select
                  className="field mt-2"
                  value={chosen}
                  onChange={(e) => {
                    setServiceId(e.target.value);
                    setTime("");
                  }}
                >
                  {services.data.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="label">
                Date
                <input
                  required
                  type="date"
                  min={dateMin}
                  className="field mt-2"
                  value={day}
                  onChange={(e) => {
                    setDay(e.target.value);
                    setTime("");
                  }}
                />
              </label>
              <ResourceState {...availability} />
              <label className="label">
                Available time
                <select
                  required
                  className="field mt-2"
                  value={availability.data?.slots.includes(time) ? time : ""}
                  onChange={(e) => setTime(e.target.value)}
                  disabled={!availability.data || !!availability.error}
                >
                  <option value="">Choose a time</option>
                  {availability.data?.slots.map((slot) => (
                    <option key={slot} value={slot}>
                      {new Date(slot).toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </option>
                  ))}
                </select>
              </label>
              {availability.data && !availability.data.slots.length && (
                <p className="text-sm text-ink-500">
                  No available times on this date. Choose another day.
                </p>
              )}
              <p className="text-xs text-ink-500">
                Times are shown in your local timezone. Reservations last 30
                minutes; overlapping service and personal bookings are blocked.
              </p>
              <label className="label">
                Notes (optional)
                <textarea
                  className="field mt-2"
                  maxLength={2000}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                />
              </label>
              {time && (
                <p className="rounded-lg bg-signal-50 p-3 text-sm text-signal-700">
                  Confirm {dateTime(time)}
                </p>
              )}
              <Button
                type="submit"
                loading={pending}
                disabled={
                  !availability.data?.slots.includes(time) ||
                  !!availability.error
                }
                className="w-full"
              >
                Confirm appointment
              </Button>
            </form>
          ) : (
            services.data && (
              <p className="text-sm text-ink-500">
                Appointments will open when a service is published.
              </p>
            )
          )}
        </Card>
        <Card title="Your visits">
          <div className="mb-5 flex gap-2">
            {["upcoming", "history", "all"].map((f) => (
              <Button
                key={f}
                size="sm"
                variant={filter === f ? "primary" : "secondary"}
                onClick={() => setFilter(f)}
              >
                {f.charAt(0).toUpperCase() + f.slice(1)}
              </Button>
            ))}
          </div>
          {mine.data && !rows.length && (
            <EmptyState
              title="No appointments here"
              body="Your confirmed visits will appear here."
            />
          )}
          {rows.map((a) => (
            <div
              key={a.id}
              className="mb-4 rounded-xl border border-ink-100 p-4"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h3 className="font-semibold">{a.service_name}</h3>
                  <p className="mt-2 text-sm text-ink-500">
                    {dateTime(a.scheduled_time)}
                  </p>
                  {a.notes && (
                    <p className="mt-2 text-sm text-ink-500">{a.notes}</p>
                  )}
                </div>
                <span className="rounded-full bg-ink-50 px-3 py-1 text-xs">
                  {a.status.replaceAll("_", " ")}
                </span>
              </div>
              {a.status === "SCHEDULED" && (
                <Button
                  className="mt-3"
                  size="sm"
                  variant="ghost"
                  onClick={() => setCancel(a.id)}
                >
                  Cancel appointment
                </Button>
              )}
            </div>
          ))}
        </Card>
      </div>
      <ConfirmDialog
        open={!!cancel}
        title="Cancel appointment?"
        body="This will release your reservation."
        confirmLabel="Cancel appointment"
        danger
        onConfirm={cancelBooking}
        onCancel={() => setCancel(null)}
      />
    </AppShell>
  );
}
