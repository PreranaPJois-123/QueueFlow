"""Shared helpers for hospital, shop and hotel bookings."""
import secrets
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.models import User, UserRole
from app.models.venues import Venue, VenueKind, VenueStaff

_REF_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I confusion
_KIND_LETTER = {VenueKind.HOSPITAL: "H", VenueKind.SHOP: "S", VenueKind.HOTEL: "R"}


def new_reference(kind: VenueKind) -> str:
    return f"QF-{_KIND_LETTER[kind]}-" + "".join(secrets.choice(_REF_ALPHABET) for _ in range(7))


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def venue_tz(venue: Venue) -> ZoneInfo:
    return ZoneInfo(venue.timezone)


def local_today(venue: Venue) -> date:
    return utcnow().astimezone(venue_tz(venue)).date()


def get_active_venue(db: Session, venue_id: str, *kinds: VenueKind, lock: bool = False) -> Venue:
    query = db.query(Venue).filter(Venue.id == venue_id)
    if lock:
        query = query.with_for_update()
    venue = query.first()
    if venue is None or not venue.is_active or (kinds and venue.kind not in kinds):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This venue is not available")
    return venue


def can_operate(db: Session, user: User, venue_id: str) -> bool:
    if user.role == UserRole.ADMIN:
        return True
    if user.role != UserRole.STAFF:
        return False
    return db.query(VenueStaff).filter(VenueStaff.venue_id == venue_id, VenueStaff.user_id == user.id).first() \
        is not None


def require_operator(db: Session, user: User, venue_id: str) -> None:
    if not can_operate(db, user, venue_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You are not assigned to this venue")


def conflict(message: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, message)
