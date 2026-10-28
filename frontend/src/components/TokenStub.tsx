import type { ReactNode } from "react";
import { relativeMinutes, venueDate, venueTime } from "../lib/format";
import type { Booking } from "../types";
import { StatusBadge } from "./ui";

/** The appointment ticket: venue and time on the left, the token on the right. */
export function TokenStub({ booking, footer }: { booking: Booking; footer?: ReactNode }) {
  const live = booking.live;
  const isTurn = booking.status === "IN_SERVICE";
  return (
    <article className="stub overflow-hidden" aria-label={`Appointment ${booking.reference}`}>
      <div className="grid sm:grid-cols-[62%_38%]">
        <div className="space-y-4 p-5 md:p-6">
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={booking.status} />
            <span className="text-xs text-ink-400">Ref {booking.reference}</span>
          </div>
          <div>
            <h2 className="text-xl font-semibold text-ink-900">{booking.offering_name}</h2>
            <p className="mt-1 text-sm text-ink-500">
              {booking.provider_name} at {booking.venue_name}
            </p>
          </div>
          <dl className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <dt className="text-xs text-ink-400">Date</dt>
              <dd className="font-medium text-ink-800">{venueDate(booking.start_at, booking.venue_timezone)}</dd>
            </div>
            <div>
              <dt className="text-xs text-ink-400">Time</dt>
              <dd className="font-medium text-ink-800">{venueTime(booking.start_at, booking.venue_timezone)}</dd>
            </div>
          </dl>
          {footer}
        </div>
        <div className={`stub-divider flex flex-col justify-center gap-3 p-5 md:p-6 ${isTurn ? "bg-amber-100" : "bg-paper-dim/40"}`}>
          <p className="text-xs text-ink-500">Your token</p>
          <p className="token-display font-display text-4xl font-bold text-ink-900 md:text-5xl">{booking.token_label}</p>
          {!live && ["CONFIRMED", "CHECKED_IN"].includes(booking.status) && (
            <p className="text-sm text-ink-500">Live queue position appears here on the day of your visit.</p>
          )}
          {live && (
            <div className="space-y-1 text-sm" aria-live="polite">
              {isTurn ? (
                <p className="font-semibold text-amber-600">It's your turn. Please go to the desk.</p>
              ) : (
                <>
                  <p className="text-ink-600">
                    Now serving <span className="font-semibold text-ink-900">{live.current_token || "nobody yet"}</span>
                  </p>
                  {live.position !== null && (
                    <p className="text-ink-600">
                      {live.position === 1 ? "You're next" : `${live.position - 1} ahead of you`}
                      {live.eta_minutes !== null && live.eta_minutes > 1 && <>, about {relativeMinutes(live.eta_minutes)} to go</>}
                    </p>
                  )}
                  {live.delay_minutes > 0 && <p className="text-amber-600">Running {live.delay_minutes} min late</p>}
                  {live.queue_status === "PAUSED" && <p className="text-amber-600">Queue paused by the venue</p>}
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </article>
  );
}
