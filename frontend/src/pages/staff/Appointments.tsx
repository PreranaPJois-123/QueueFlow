import { useClock } from "../../lib/useClock";
import { useEffect, useState } from "react";
import { api, extractErrorMessage } from "../../lib/api";
import { AppShell } from "../../components/AppShell";
import { Button } from "../../components/Button";
import { EmptyState, ErrorState, Skeleton } from "../../components/States";
import { useToast } from "../../components/Toast";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { dateTime } from "../../lib/format";
import type { Appointment } from "../../types";

interface StaffAppointment extends Appointment {
  customer_name: string;
  service_name: string;
}

export default function StaffAppointments() {
  const now = useClock();
  const [appointments, setAppointments] = useState<StaffAppointment[] | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const { push } = useToast();
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("ALL");
  const [period, setPeriod] = useState("ALL");
  const [confirm, setConfirm] = useState<StaffAppointment | null>(null);

  async function load() {
    try {
      const { data } = await api.get<StaffAppointment[]>(
        "/api/staff/appointments",
      );
      setAppointments(data);
      setError(null);
    } catch (err) {
      setError(extractErrorMessage(err));
      setAppointments([]);
    }
  }

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    let loading = false;
    async function refresh() {
      if (loading) return;
      loading = true;
      try {
        const { data } = await api.get<StaffAppointment[]>(
          "/api/staff/appointments",
          { signal: controller.signal },
        );
        if (active) {
          setAppointments(data);
          setError(null);
        }
      } catch (e) {
        if (active) {
          setError(extractErrorMessage(e));
          setAppointments((previous) => previous ?? []);
        }
      } finally {
        loading = false;
      }
    }
    void refresh();
    const timer = setInterval(() => {
      void refresh();
    }, 15000);
    return () => {
      active = false;
      controller.abort();
      clearInterval(timer);
    };
  }, []);

  const filtered = appointments?.filter(
    (a) =>
      `${a.customer_name} ${a.service_name}`
        .toLowerCase()
        .includes(search.toLowerCase()) &&
      (filter === "ALL" || a.status === filter) &&
      (period === "ALL" ||
        (period === "TODAY"
          ? new Date(a.scheduled_time).toDateString() ===
            new Date(now).toDateString()
          : new Date(a.scheduled_time).getTime() >= now)),
  );

  async function act(
    appointment: StaffAppointment,
    action: "check-in" | "complete" | "no-show",
  ) {
    setPendingId(appointment.id);
    try {
      await api.post(`/api/staff/appointments/${appointment.id}/${action}`);
      push("Appointment updated", "success");
      setConfirm(null);
      await load();
    } catch (err) {
      push(extractErrorMessage(err), "error");
    } finally {
      setPendingId(null);
    }
  }

  return (
    <AppShell variant="staff">
      <h1 className="text-xl font-semibold text-ink-900">Appointments</h1>
      <p className="mt-1 text-sm text-ink-500">
        Customer bookings and visit status across services.
      </p>
      {error && (
        <div className="mt-6">
          <ErrorState message={error} />
        </div>
      )}
      <div className="mt-6 flex flex-wrap gap-3">
        <input
          className="field max-w-xs"
          aria-label="Search appointments"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Customer or service…"
        />
        <select
          className="field max-w-xs"
          aria-label="Appointment status"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        >
          {[
            "ALL",
            "SCHEDULED",
            "CHECKED_IN",
            "COMPLETED",
            "CANCELLED",
            "NO_SHOW",
          ].map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
        <select
          aria-label="Appointment period"
          className="field max-w-xs"
          value={period}
          onChange={(e) => setPeriod(e.target.value)}
        >
          {["ALL", "TODAY", "UPCOMING"].map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
        <Button variant="secondary" onClick={load}>
          Refresh
        </Button>
      </div>
      <div className="mt-6">
        {appointments === null ? (
          <Skeleton className="h-40 w-full" />
        ) : filtered?.length === 0 && !error ? (
          <EmptyState
            title="No appointments yet"
            body="Bookings will appear here when customers schedule a service."
          />
        ) : (
          <ul className="space-y-3">
            {filtered?.map((appointment) => (
              <li
                key={appointment.id}
                className="rounded-xl border border-ink-100 bg-white p-5"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="font-medium text-ink-900">
                      {appointment.customer_name}
                    </p>
                    <p className="mt-1 text-sm text-ink-600">
                      {appointment.service_name} ·{" "}
                      {dateTime(appointment.scheduled_time)}
                    </p>
                    {appointment.notes && (
                      <p className="mt-2 text-sm text-ink-500">
                        {appointment.notes}
                      </p>
                    )}
                  </div>
                  <span className="rounded-md bg-ink-50 px-2 py-1 text-xs font-medium text-ink-600">
                    {appointment.status.replaceAll("_", " ").toLowerCase()}
                  </span>
                </div>
                {appointment.status === "SCHEDULED" && (
                  <div className="mt-4 flex flex-wrap gap-2">
                    <Button
                      size="sm"
                      loading={pendingId === appointment.id}
                      onClick={() => act(appointment, "check-in")}
                    >
                      Check in
                    </Button>
                    <Button
                      size="sm"
                      variant="secondary"
                      disabled={pendingId === appointment.id}
                      onClick={() => setConfirm(appointment)}
                    >
                      No show
                    </Button>
                  </div>
                )}
                {appointment.status === "CHECKED_IN" && (
                  <Button
                    size="sm"
                    className="mt-4"
                    loading={pendingId === appointment.id}
                    onClick={() => act(appointment, "complete")}
                  >
                    Complete visit
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
      <ConfirmDialog
        open={!!confirm}
        title="Mark as no show?"
        body="This appointment will no longer be active."
        danger
        onConfirm={() => (confirm ? act(confirm, "no-show") : undefined)}
        onCancel={() => setConfirm(null)}
      />
    </AppShell>
  );
}
