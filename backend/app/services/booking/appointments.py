"""Hospital and shop appointments with queue tokens.

Token policy
------------
Each provider has one queue per venue-local service date (``QueueDay``).
Tokens are issued from that queue's counter in booking order
(``<PREFIX>-001``, ``-002``...), under a row lock, so concurrent bookings can
never receive the same token. Tokens are never reused, even after a
cancellation. Customers are served in appointment-time order; the token
identifies the customer at the desk. Rescheduling within the same queue keeps
the token; moving to another provider or date issues a new one.

Consistency
-----------
Booking runs in one transaction: the provider row is locked (serialising
bookings for that provider), the slot is re-validated against current
bookings, then the queue-day row is locked to issue the token. A PostgreSQL
exclusion constraint independently rejects overlapping active bookings.
"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.models import NotificationType, User, gen_uuid
from app.models.venues import (
    ACTIVE_BOOKING_STATUSES, Booking, BookingStatus, Offering, Provider, QueueDay, VenueKind,
)
from app.services import audit
from app.services.booking import queue_ops
from app.services.booking.common import as_utc, conflict, get_active_venue, new_reference, utcnow, venue_tz
from app.services.booking.slots import authorised_providers, provider_slots, validate_service_date
from app.services.notify import notify


def _fmt_local(venue, when: datetime) -> str:
    return as_utc(when).astimezone(venue_tz(venue)).strftime("%a %d %b, %I:%M %p").replace(" 0", " ")


def _lock_provider(db: Session, provider_id: str) -> Provider:
    return db.query(Provider).filter(Provider.id == provider_id).populate_existing().with_for_update().one()


def _queue_day(db: Session, provider_id: str, service_date) -> QueueDay:
    db.execute(insert(QueueDay).values(id=gen_uuid(), provider_id=provider_id, service_date=service_date,
                                       next_token=1, status="OPEN", delay_minutes=0)
               .on_conflict_do_nothing(constraint="uq_queue_day"))
    return (db.query(QueueDay).filter(QueueDay.provider_id == provider_id, QueueDay.service_date == service_date)
            .populate_existing().with_for_update().one())


def _issue_token(db: Session, provider: Provider, service_date) -> tuple[QueueDay, int, str]:
    day = _queue_day(db, provider.id, service_date)
    number = day.next_token
    day.next_token = number + 1
    return day, number, f"{provider.token_prefix}-{number:03d}"


def _customer_overlap(db: Session, customer_id: str, start: datetime, end: datetime,
                      exclude_id: Optional[str] = None) -> bool:
    query = db.query(Booking.id).filter(Booking.customer_id == customer_id,
                                        Booking.status.in_(ACTIVE_BOOKING_STATUSES),
                                        Booking.start_at < end, Booking.end_at > start)
    if exclude_id:
        query = query.filter(Booking.id != exclude_id)
    return query.first() is not None


def _load_offering(db: Session, venue_id: str, offering_id: str) -> Offering:
    offering = db.get(Offering, offering_id)
    if offering is None or offering.venue_id != venue_id or not offering.is_active:
        raise HTTPException(404, "This service is not offered at the selected venue")
    return offering


def _validated_slot(db, venue, offering, provider, start_at, exclude_booking_id=None):
    start_at = as_utc(start_at)
    day = start_at.astimezone(venue_tz(venue)).date()
    validate_service_date(venue, day)
    for slot in provider_slots(db, venue, offering, provider, day, exclude_booking_id):
        if slot.start_at == start_at:
            return slot, day
    raise conflict("That time is no longer available. Please choose another slot.")


def find_by_idempotency(db: Session, customer_id: str, key: Optional[str]) -> Optional[Booking]:
    if not key:
        return None
    return db.query(Booking).filter(Booking.customer_id == customer_id, Booking.idempotency_key == key).first()


def create_booking(db: Session, customer: User, *, venue_id: str, offering_id: str, start_at: datetime,
                   provider_id: Optional[str] = None, notes: Optional[str] = None,
                   idempotency_key: Optional[str] = None, source: str = "web") -> tuple[Booking, bool]:
    """Returns (booking, created). A repeated idempotency key returns the original booking."""
    existing = find_by_idempotency(db, customer.id, idempotency_key)
    if existing:
        return existing, False
    venue = get_active_venue(db, venue_id, VenueKind.HOSPITAL, VenueKind.SHOP)
    offering = _load_offering(db, venue.id, offering_id)
    candidates = authorised_providers(db, offering, provider_id)
    if not candidates:
        raise HTTPException(404, "The selected provider does not offer this service")

    last_error: Optional[HTTPException] = None
    for candidate in candidates:  # "any available": first provider with the slot free
        provider = _lock_provider(db, candidate.id)
        try:
            slot, day = _validated_slot(db, venue, offering, provider, start_at)
        except HTTPException as error:
            last_error = error
            continue
        if _customer_overlap(db, customer.id, slot.start_at, slot.end_at):
            db.rollback()
            raise conflict("You already have another appointment at this time")
        queue_day, number, label = _issue_token(db, provider, day)
        booking = Booking(reference=new_reference(venue.kind), customer_id=customer.id, venue_id=venue.id,
                          offering_id=offering.id, provider_id=provider.id, queue_day_id=queue_day.id,
                          start_at=slot.start_at, end_at=slot.end_at, service_date=day, token_number=number,
                          token_label=label, status=BookingStatus.CONFIRMED,
                          notes=(notes or None), idempotency_key=idempotency_key)
        db.add(booking)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            repeated = find_by_idempotency(db, customer.id, idempotency_key)
            if repeated:
                return repeated, False
            raise conflict("That time was just booked by someone else. Please choose another slot.")
        audit.record(db, "booking.created", actor_id=customer.id, entity_type="booking", entity_id=booking.id,
                     to_status=BookingStatus.CONFIRMED.value, source=source)
        notify(db, customer.id, NotificationType.BOOKING_CONFIRMED,
               f"Booked: {offering.name} at {venue.name}, {_fmt_local(venue, slot.start_at)}. "
               f"Token {label}, reference {booking.reference}.",
               dedupe_key=f"confirmed:{booking.id}", booking_id=booking.id)
        queue_ops.enqueue_queue_refresh(db, queue_day.id)
        db.commit()
        db.refresh(booking)
        return booking, True
    db.rollback()
    raise last_error or conflict("That time is no longer available")


def _lock_own_booking(db: Session, customer: User, reference: str) -> Booking:
    booking = (db.query(Booking).filter(Booking.reference == reference).populate_existing().with_for_update().first())
    # 404 (not 403) for other users' bookings so references cannot be probed.
    if booking is None or booking.customer_id != customer.id:
        raise HTTPException(404, "Booking not found")
    return booking


def _check_cutoff(booking: Booking) -> None:
    venue = booking.venue
    if utcnow() > as_utc(booking.start_at) - timedelta(minutes=venue.cancel_cutoff_minutes):
        raise conflict(f"Changes close {venue.cancel_cutoff_minutes} minutes before the appointment. "
                       f"Please contact {venue.name} directly.")


def cancel_booking(db: Session, customer: User, reference: str, source: str = "web") -> Booking:
    booking = _lock_own_booking(db, customer, reference)
    if booking.status != BookingStatus.CONFIRMED:
        raise conflict(f"A booking that is {booking.status.value.lower().replace('_', ' ')} cannot be cancelled")
    _check_cutoff(booking)
    booking.status = BookingStatus.CANCELLED
    booking.cancelled_at = utcnow()
    audit.record(db, "booking.status", actor_id=customer.id, entity_type="booking", entity_id=booking.id,
                 from_status="CONFIRMED", to_status="CANCELLED", source=source)
    notify(db, customer.id, NotificationType.BOOKING_CANCELLED,
           f"Cancelled: {booking.offering.name} at {booking.venue.name} ({booking.reference}).",
           dedupe_key=f"cancelled:{booking.id}", booking_id=booking.id)
    queue_ops.enqueue_queue_refresh(db, booking.queue_day_id)
    db.commit()
    db.refresh(booking)
    return booking


def reschedule_booking(db: Session, customer: User, reference: str, new_start: datetime,
                       provider_id: Optional[str] = None) -> Booking:
    booking = _lock_own_booking(db, customer, reference)
    if booking.status != BookingStatus.CONFIRMED:
        raise conflict("Only confirmed bookings can be rescheduled")
    _check_cutoff(booking)
    venue = get_active_venue(db, booking.venue_id, VenueKind.HOSPITAL, VenueKind.SHOP)
    offering = _load_offering(db, venue.id, booking.offering_id)
    target_id = provider_id or booking.provider_id
    if not authorised_providers(db, offering, target_id):
        raise HTTPException(404, "The selected provider does not offer this service")
    for pid in sorted({booking.provider_id, target_id}):  # fixed lock order prevents deadlocks
        _lock_provider(db, pid)
    provider = db.get(Provider, target_id)
    slot, day = _validated_slot(db, venue, offering, provider, new_start, exclude_booking_id=booking.id)
    if _customer_overlap(db, customer.id, slot.start_at, slot.end_at, exclude_id=booking.id):
        raise conflict("You already have another appointment at this time")
    old_queue_day = booking.queue_day_id
    old_start = booking.start_at
    if day != booking.service_date or provider.id != booking.provider_id:
        queue_day, number, label = _issue_token(db, provider, day)
        booking.queue_day_id, booking.token_number, booking.token_label = queue_day.id, number, label
        booking.provider_id, booking.service_date = provider.id, day
    booking.start_at, booking.end_at = slot.start_at, slot.end_at
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise conflict("That time was just booked by someone else. Please choose another slot.")
    audit.record(db, "booking.rescheduled", actor_id=customer.id, entity_type="booking", entity_id=booking.id,
                 old_start=as_utc(old_start).isoformat(), new_start=slot.start_at.isoformat())
    notify(db, customer.id, NotificationType.BOOKING_UPDATED,
           f"Rescheduled: {offering.name} at {venue.name} is now {_fmt_local(venue, slot.start_at)}. "
           f"Token {booking.token_label}.", booking_id=booking.id)
    queue_ops.enqueue_queue_refresh(db, old_queue_day)
    queue_ops.enqueue_queue_refresh(db, booking.queue_day_id)
    db.commit()
    db.refresh(booking)
    return booking
