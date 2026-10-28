"""Queue-day operations: wait estimates, turn alerts and staff actions.

Wait estimate
-------------
For each active booking, in appointment order, the expected start is::

    cursor   = now, or the in-service booking's expected end if later
    for each booking ahead:  cursor = max(cursor, its start + delay) + its duration
    expected = max(cursor, own start + delay)

Durations are the median of the provider's last 30 completed visits for that
service (when at least 5 exist), otherwise the configured service duration.
Estimates are recomputed on every queue change and once a minute by the
monitor, so alerts track actual progress rather than booking time.

Turn alerts
-----------
When an estimate first drops to ``TURN_ALERT_MINUTES`` (default 20) or less,
one TURN_APPROACHING notification is created, keyed by booking and slot. If
the estimate later rises above the threshold and falls again, no second
alert is sent; rescheduling creates a new key and therefore a new alert.
"""
from datetime import date, datetime, timedelta
from statistics import median
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.models.models import NotificationType, User
from app.models.venues import (
    ACTIVE_BOOKING_STATUSES, Booking, BookingStatus, Provider, QueueDay, QueueDayStatus, Venue,
)
from app.services import audit, realtime
from app.services.booking.common import as_utc, conflict, local_today, require_operator, utcnow
from app.services.notify import notify

TRANSITIONS = {
    "check-in": ({BookingStatus.CONFIRMED}, BookingStatus.CHECKED_IN),
    "start": ({BookingStatus.CONFIRMED, BookingStatus.CHECKED_IN}, BookingStatus.IN_SERVICE),
    "complete": ({BookingStatus.IN_SERVICE}, BookingStatus.COMPLETED),
    "no-show": ({BookingStatus.CONFIRMED, BookingStatus.CHECKED_IN}, BookingStatus.NO_SHOW),
    "cancel": ({BookingStatus.CONFIRMED, BookingStatus.CHECKED_IN}, BookingStatus.CANCELLED),
}


def _duration_minutes(db: Session, booking: Booking, cache: dict) -> float:
    key = (booking.provider_id, booking.offering_id)
    if key not in cache:
        rows = (db.query(Booking.started_at, Booking.completed_at)
                .filter(Booking.provider_id == booking.provider_id, Booking.offering_id == booking.offering_id,
                        Booking.status == BookingStatus.COMPLETED, Booking.started_at.isnot(None),
                        Booking.completed_at.isnot(None))
                .order_by(Booking.completed_at.desc()).limit(30).all())
        samples = [(as_utc(c) - as_utc(s)).total_seconds() / 60 for s, c in rows if c > s]
        cache[key] = median(samples) if len(samples) >= 5 else float(booking.offering.duration_minutes)
    return cache[key]


def snapshot(db: Session, queue_day: QueueDay, now: Optional[datetime] = None) -> dict:
    now = now or utcnow()
    active = (db.query(Booking).options(joinedload(Booking.offering))
              .filter(Booking.queue_day_id == queue_day.id, Booking.status.in_(ACTIVE_BOOKING_STATUSES))
              .order_by(Booking.start_at, Booking.token_number).all())
    delay = timedelta(minutes=queue_day.delay_minutes)
    cache: dict = {}
    serving = next((b for b in active if b.status == BookingStatus.IN_SERVICE), None)
    cursor = now
    if serving is not None:
        started = as_utc(serving.started_at or now)
        cursor = max(now, started + timedelta(minutes=_duration_minutes(db, serving, cache)))
    entries: dict[str, dict] = {}
    position = 0
    for booking in active:
        if booking is serving:
            entries[booking.id] = {"position": 0, "eta_minutes": 0, "expected_start": as_utc(booking.started_at or now)}
            continue
        position += 1
        expected = max(cursor, as_utc(booking.start_at) + delay)
        entries[booking.id] = {"position": position,
                               "eta_minutes": max(0, round((expected - now).total_seconds() / 60)),
                               "expected_start": expected}
        cursor = expected + timedelta(minutes=_duration_minutes(db, booking, cache))
    return {"queue_day_id": queue_day.id, "status": queue_day.status.value, "delay_minutes": queue_day.delay_minutes,
            "current_token": serving.token_label if serving else None, "waiting": position,
            "bookings": active, "entries": entries}


def booking_live(db: Session, booking: Booking) -> dict:
    """Customer-safe live view of one booking (no data about other customers)."""
    queue_day = db.get(QueueDay, booking.queue_day_id)
    snap = snapshot(db, queue_day)
    entry = snap["entries"].get(booking.id)
    return {"queue_status": snap["status"], "current_token": snap["current_token"],
            "delay_minutes": snap["delay_minutes"], "position": entry["position"] if entry else None,
            "eta_minutes": entry["eta_minutes"] if entry else None,
            "expected_start": entry["expected_start"] if entry else None}


def refresh_queue_day(db: Session, queue_day_id: str) -> None:
    """Recompute estimates inside the current transaction, push each customer
    their own update and create any due turn alerts (published on commit)."""
    db.flush()
    queue_day = db.get(QueueDay, queue_day_id)
    if queue_day is None:
        return
    snap = snapshot(db, queue_day)
    for booking in snap["bookings"]:
        entry = snap["entries"][booking.id]
        if booking.service_date != local_today(booking.venue):
            continue  # live positions and turn alerts only apply on the visit day
        realtime.enqueue(db, f"user:{booking.customer_id}", {"type": "booking_update", "data": {
            "reference": booking.reference, "status": booking.status.value, "position": entry["position"],
            "eta_minutes": entry["eta_minutes"], "current_token": snap["current_token"],
            "delay_minutes": snap["delay_minutes"], "queue_status": snap["status"]}})
        if booking.status in (BookingStatus.CONFIRMED, BookingStatus.CHECKED_IN) \
                and entry["eta_minutes"] <= settings.TURN_ALERT_MINUTES:
            minutes = entry["eta_minutes"]
            when = (f"in approximately {minutes} minutes" if minutes > 2 else "very shortly")
            notify(db, booking.customer_id, NotificationType.TURN_APPROACHING,
                   f"Your appointment is approaching. Your turn is expected {when}. Please be ready. "
                   f"Token {booking.token_label} at {booking.venue.name}.",
                   dedupe_key=f"turn:{booking.id}:{as_utc(booking.start_at).isoformat()}", booking_id=booking.id)


def enqueue_queue_refresh(db: Session, queue_day_id: str) -> None:
    refresh_queue_day(db, queue_day_id)


def _lock_queue_day(db: Session, queue_day_id: str) -> QueueDay:
    return db.query(QueueDay).filter(QueueDay.id == queue_day_id).populate_existing().with_for_update().one()


def _get_queue_day(db: Session, user: User, provider_id: str, day: date, lock: bool = True) -> QueueDay:
    provider = db.get(Provider, provider_id)
    if provider is None:
        raise HTTPException(404, "Provider not found")
    require_operator(db, user, provider.venue_id)
    query = db.query(QueueDay).filter(QueueDay.provider_id == provider_id, QueueDay.service_date == day)
    queue_day = query.populate_existing().with_for_update().first() if lock else query.first()
    if queue_day is None:
        raise HTTPException(404, "No bookings exist for this provider on that date")
    return queue_day


def staff_transition(db: Session, user: User, booking_id: str, action: str) -> Booking:
    if action not in TRANSITIONS:
        raise HTTPException(404, "Unknown action")
    allowed, target = TRANSITIONS[action]
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if booking is None:
        raise HTTPException(404, "Booking not found")
    require_operator(db, user, booking.venue_id)
    queue_day = _lock_queue_day(db, booking.queue_day_id)  # serialises all actions on this queue
    db.refresh(booking, with_for_update=True)
    if booking.status not in allowed:
        raise conflict(f"Cannot {action.replace('-', ' ')} a booking that is "
                       f"{booking.status.value.lower().replace('_', ' ')}")
    now = utcnow()
    if action in ("start", "check-in") and booking.service_date != local_today(booking.venue):
        raise conflict("Only today's bookings can be checked in or started")
    if action == "start":
        if queue_day.status == QueueDayStatus.PAUSED:
            raise conflict("Resume the queue before starting the next visit")
        busy = db.query(Booking.id).filter(Booking.queue_day_id == queue_day.id,
                                           Booking.status == BookingStatus.IN_SERVICE).first()
        if busy:
            raise conflict("Complete the current visit before starting another")
    previous = booking.status
    booking.status = target
    if target == BookingStatus.CHECKED_IN:
        booking.checked_in_at = now
    elif target == BookingStatus.IN_SERVICE:
        booking.started_at = now
        booking.checked_in_at = booking.checked_in_at or now
    elif target == BookingStatus.COMPLETED:
        booking.completed_at = now
    elif target == BookingStatus.CANCELLED:
        booking.cancelled_at = now
    audit.record(db, "booking.status", actor_id=user.id, entity_type="booking", entity_id=booking.id,
                 from_status=previous.value, to_status=target.value, source="staff")
    venue = booking.venue
    if target == BookingStatus.IN_SERVICE:
        notify(db, booking.customer_id, NotificationType.CALLED,
               f"It's your turn: please proceed to {booking.provider.name} at {venue.name}. "
               f"Token {booking.token_label}.", dedupe_key=f"called:{booking.id}", booking_id=booking.id)
    elif target == BookingStatus.CANCELLED:
        notify(db, booking.customer_id, NotificationType.BOOKING_CANCELLED,
               f"{venue.name} cancelled your appointment {booking.reference}. Please contact them or rebook.",
               dedupe_key=f"cancelled:{booking.id}", booking_id=booking.id)
    elif target == BookingStatus.NO_SHOW:
        notify(db, booking.customer_id, NotificationType.BOOKING_UPDATED,
               f"Your appointment {booking.reference} at {venue.name} was marked as missed.",
               dedupe_key=f"noshow:{booking.id}", booking_id=booking.id)
    refresh_queue_day(db, queue_day.id)
    db.commit()
    db.refresh(booking)
    return booking


def call_next(db: Session, user: User, provider_id: str, day: date) -> Booking:
    queue_day = _get_queue_day(db, user, provider_id, day)
    candidates = (db.query(Booking).filter(Booking.queue_day_id == queue_day.id,
                                           Booking.status.in_([BookingStatus.CHECKED_IN, BookingStatus.CONFIRMED]))
                  .order_by((Booking.status != BookingStatus.CHECKED_IN), Booking.start_at).all())
    if not candidates:
        raise conflict("Nobody is waiting in this queue")
    return staff_transition(db, user, candidates[0].id, "start")


def set_queue_state(db: Session, user: User, provider_id: str, day: date, *, paused: Optional[bool] = None,
                    delay_minutes: Optional[int] = None) -> QueueDay:
    queue_day = _get_queue_day(db, user, provider_id, day)
    if paused is not None:
        queue_day.status = QueueDayStatus.PAUSED if paused else QueueDayStatus.OPEN
        audit.record(db, "queue.paused" if paused else "queue.resumed", actor_id=user.id, entity_type="queue_day",
                     entity_id=queue_day.id)
    if delay_minutes is not None:
        if not 0 <= delay_minutes <= 600:
            raise HTTPException(422, "Delay must be between 0 and 600 minutes")
        changed = delay_minutes != queue_day.delay_minutes
        queue_day.delay_minutes = delay_minutes
        audit.record(db, "queue.delay", actor_id=user.id, entity_type="queue_day", entity_id=queue_day.id,
                     delay_minutes=delay_minutes)
        if changed and delay_minutes > 0:
            provider = db.get(Provider, provider_id)
            for booking in db.query(Booking).filter(Booking.queue_day_id == queue_day.id,
                                                    Booking.status.in_(ACTIVE_BOOKING_STATUSES)).all():
                if booking.status == BookingStatus.IN_SERVICE:
                    continue
                notify(db, booking.customer_id, NotificationType.SERVICE_DELAY,
                       f"{provider.name} at {booking.venue.name} is running about {delay_minutes} minutes behind "
                       f"schedule. Your wait estimate has been updated.",
                       dedupe_key=f"delay:{queue_day.id}:{delay_minutes}:{booking.id}", booking_id=booking.id)
    refresh_queue_day(db, queue_day.id)
    db.commit()
    db.refresh(queue_day)
    return queue_day


def board(db: Session, user: User, venue: Venue, day: date) -> list[dict]:
    require_operator(db, user, venue.id)
    result = []
    for provider in db.query(Provider).filter(Provider.venue_id == venue.id).order_by(Provider.name).all():
        queue_day = db.query(QueueDay).filter(QueueDay.provider_id == provider.id,
                                              QueueDay.service_date == day).first()
        snap = snapshot(db, queue_day) if queue_day else None
        bookings = []
        if queue_day:
            for b in (db.query(Booking).options(joinedload(Booking.customer), joinedload(Booking.offering))
                      .filter(Booking.queue_day_id == queue_day.id).order_by(Booking.start_at).all()):
                entry = snap["entries"].get(b.id, {})
                bookings.append({"id": b.id, "reference": b.reference, "token_label": b.token_label,
                                 "status": b.status.value, "start_at": as_utc(b.start_at), "end_at": as_utc(b.end_at),
                                 "customer_name": b.customer.full_name, "offering_name": b.offering.name,
                                 "notes": b.notes, "position": entry.get("position"),
                                 "eta_minutes": entry.get("eta_minutes")})
        result.append({"provider_id": provider.id, "provider_name": provider.name, "provider_title": provider.title,
                       "is_active": provider.is_active, "status": snap["status"] if snap else "OPEN",
                       "delay_minutes": snap["delay_minutes"] if snap else 0,
                       "current_token": snap["current_token"] if snap else None,
                       "waiting": snap["waiting"] if snap else 0, "bookings": bookings})
    return result


def run_monitor_once(db: Session) -> int:
    """Recompute estimates for queues with visits around now; returns queues refreshed."""
    now = utcnow()
    ids = [row[0] for row in db.query(Booking.queue_day_id).filter(
        Booking.status.in_(ACTIVE_BOOKING_STATUSES), Booking.start_at > now - timedelta(hours=8),
        Booking.start_at < now + timedelta(hours=8)).distinct().all()]
    for queue_day_id in ids:
        refresh_queue_day(db, queue_day_id)
    db.commit()
    return len(ids)
