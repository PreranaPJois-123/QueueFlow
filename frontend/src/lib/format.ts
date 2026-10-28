export const activeStatus = (status: string) =>
  ["WAITING", "CALLED", "SERVING"].includes(status);
export const dateTime = (value: string) =>
  new Date(
    value.endsWith("Z") || /[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`,
  ).toLocaleString();
export const predictionLabel = (source: string) =>
  source === "ml_knn"
    ? "ML estimate · historical nearest neighbours"
    : source === "calculated_history"
      ? "Calculated from recent service history"
      : "Calculated · configured service duration";

/** Format an instant in the venue's own timezone (bookings are venue-local). */
export function venueTime(iso: string, timeZone: string, opts: Intl.DateTimeFormatOptions = {}) {
  return new Intl.DateTimeFormat("en-IN", {
    timeZone, hour: "numeric", minute: "2-digit", ...opts,
  }).format(new Date(iso));
}

export function venueDate(iso: string, timeZone: string) {
  return new Intl.DateTimeFormat("en-IN", { timeZone, weekday: "short", day: "numeric", month: "short" })
    .format(new Date(iso));
}

/** Calendar date (YYYY-MM-DD, no timezone) for display. */
export function calendarDate(value: string, opts: Intl.DateTimeFormatOptions = {}) {
  const [y, m, d] = value.split("-").map(Number);
  return new Intl.DateTimeFormat("en-IN", { weekday: "short", day: "numeric", month: "short", year: "numeric",
    timeZone: "UTC", ...opts }).format(new Date(Date.UTC(y, m - 1, d)));
}

export function money(amount: string | number | null | undefined, currency = "INR") {
  if (amount === null || amount === undefined) return "";
  return new Intl.NumberFormat("en-IN", { style: "currency", currency, maximumFractionDigits: 2 })
    .format(Number(amount));
}

/** Today's date (YYYY-MM-DD) in a timezone. */
export function todayIn(timeZone: string, plusDays = 0) {
  const d = new Date(Date.now() + plusDays * 86400000);
  return new Intl.DateTimeFormat("en-CA", { timeZone, year: "numeric", month: "2-digit", day: "2-digit" }).format(d);
}

export function addDays(isoDate: string, days: number) {
  const [y, m, d] = isoDate.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d + days)).toISOString().slice(0, 10);
}

export function relativeMinutes(minutes: number | null | undefined) {
  if (minutes === null || minutes === undefined) return "";
  if (minutes <= 1) return "now";
  if (minutes < 60) return `${minutes} min`;
  const h = Math.floor(minutes / 60);
  return `${h} h ${minutes % 60 ? `${minutes % 60} min` : ""}`.trim();
}

export function humanStatus(status: string) {
  return status.charAt(0) + status.slice(1).toLowerCase().replace(/_/g, " ");
}
