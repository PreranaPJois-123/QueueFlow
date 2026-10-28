"""Appointment slot generation from provider schedules.

Slots for an offering start at each schedule window's opening time and step
by the offering's duration; a slot must end within the window. A slot is
offered only if it is after the venue's minimum notice, within the booking
horizon, and does not overlap any active booking of that provider.
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterable, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.venues import (
    ACTIVE_BOOKING_STATUSES, Booking, Offering, Provider, ProviderOffering, QueueDay, QueueDayStatus, Venue,
)
from app.services.booking.common import as_utc, local_today, utcnow, venue_tz


@dataclass(frozen=True)
class Slot:
    start_at: datetime
    end_at: datetime
    provider_id: str


def validate_service_date(venue: Venue, day: date) -> None:
    today = local_today(venue)
    if day < today:
        raise HTTPException(422, "Choose today or a future date")
    if day > today + timedelta(days=venue.booking_horizon_days):
        raise HTTPException(422, f"Bookings open up to {venue.booking_horizon_days} days ahead")


def authorised_providers(db: Session, offering: Offering, provider_id: Optional[str] = None) -> list[Provider]:
    query = (db.query(Provider).join(ProviderOffering, ProviderOffering.provider_id == Provider.id)
             .filter(ProviderOffering.offering_id == offering.id, Provider.is_active.is_(True),
                     Provider.venue_id == offering.venue_id))
    if provider_id:
        query = query.filter(Provider.id == provider_id)
    return query.order_by(Provider.name).all()


def _busy_ranges(db: Session, provider_id: str, start: datetime, end: datetime,
                 exclude_booking_id: Optional[str]) -> list[tuple[datetime, datetime]]:
    query = db.query(Booking.start_at, Booking.end_at).filter(
        Booking.provider_id == provider_id, Booking.status.in_(ACTIVE_BOOKING_STATUSES),
        Booking.start_at < end, Booking.end_at > start)
    if exclude_booking_id:
        query = query.filter(Booking.id != exclude_booking_id)
    return [(as_utc(s), as_utc(e)) for s, e in query.all()]


def provider_slots(db: Session, venue: Venue, offering: Offering, provider: Provider, day: date,
                   exclude_booking_id: Optional[str] = None) -> list[Slot]:
    tz = venue_tz(venue)
    duration = timedelta(minutes=offering.duration_minutes)
    paused = db.query(QueueDay.id).filter(QueueDay.provider_id == provider.id, QueueDay.service_date == day,
                                          QueueDay.status == QueueDayStatus.PAUSED).first()
    if paused:
        return []
    candidates: list[tuple[datetime, datetime]] = []
    for window in provider.schedules:
        if window.weekday != day.weekday():
            continue
        cursor = datetime.combine(day, window.start_time, tzinfo=tz)
        close = datetime.combine(day, window.end_time, tzinfo=tz)
        while cursor + duration <= close:
            candidates.append((as_utc(cursor), as_utc(cursor + duration)))
            cursor += duration
    if not candidates:
        return []
    earliest = utcnow() + timedelta(minutes=venue.min_notice_minutes)
    busy = _busy_ranges(db, provider.id, candidates[0][0], candidates[-1][1], exclude_booking_id)
    return [Slot(s, e, provider.id) for s, e in sorted(set(candidates))
            if s >= earliest and not any(s < be and e > bs for bs, be in busy)]


def available_slots(db: Session, venue: Venue, offering: Offering, day: date,
                    providers: Iterable[Provider]) -> list[Slot]:
    validate_service_date(venue, day)
    slots: list[Slot] = []
    for provider in providers:
        slots.extend(provider_slots(db, venue, offering, provider, day))
    return sorted(slots, key=lambda s: (s.start_at, s.provider_id))
