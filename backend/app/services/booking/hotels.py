"""Hotel availability, pricing and reservations.

Inventory: ``room_inventory`` holds rooms sold per room type and night. A
reservation locks its room type row, then for every night runs a guarded
``UPDATE ... SET booked = booked + n WHERE booked + n <= total`` and aborts
the whole transaction if any night is full, so the last room can never be sold
twice. Prices are computed on the server with ``Decimal``:
``subtotal = nightly_rate x nights x rooms``, ``taxes = subtotal x tax_rate``
(rounded half-up to 0.01), ``total = subtotal + taxes``.

Cancellation policy: free until ``free_cancellation_hours`` before the
check-in time; later cancellations record a fee of one night per room,
payable to the hotel (QueueFlow does not process payments).
"""
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.models import NotificationType, User
from app.models.venues import Reservation, ReservationStatus, RoomInventory, RoomType, Venue, VenueKind
from app.services import audit
from app.services.booking.common import (
    conflict, get_active_venue, local_today, new_reference, require_operator, utcnow, venue_tz,
)
from app.services.notify import notify

MAX_NIGHTS = 30
MAX_ADVANCE_DAYS = 365
CENT = Decimal("0.01")


def nights_between(check_in: date, check_out: date) -> list[date]:
    return [check_in + timedelta(days=i) for i in range((check_out - check_in).days)]


def validate_stay(venue: Venue, room_type: RoomType, check_in: date, check_out: date, guests: int, rooms: int) -> None:
    validate_dates(venue, check_in, check_out, rooms)
    if guests < 1 or guests > room_type.max_occupancy * rooms:
        raise HTTPException(422, f"{room_type.name} sleeps up to {room_type.max_occupancy} guests per room")


def validate_dates(venue: Venue, check_in: date, check_out: date, rooms: int = 1) -> None:
    today = local_today(venue)
    if check_in < today:
        raise HTTPException(422, "Check-in cannot be in the past")
    if check_out <= check_in:
        raise HTTPException(422, "Check-out must be after check-in")
    if (check_out - check_in).days > MAX_NIGHTS:
        raise HTTPException(422, f"Stays are limited to {MAX_NIGHTS} nights")
    if check_in > today + timedelta(days=MAX_ADVANCE_DAYS):
        raise HTTPException(422, "Reservations open up to one year ahead")
    if not 1 <= rooms <= 5:
        raise HTTPException(422, "Book between 1 and 5 rooms")


def _room_type(db: Session, venue: Venue, room_type_id: str, lock: bool = False) -> RoomType:
    query = db.query(RoomType).filter(RoomType.id == room_type_id)
    if lock:
        query = query.populate_existing().with_for_update()
    room_type = query.first()
    if room_type is None or room_type.venue_id != venue.id or not room_type.is_active:
        raise HTTPException(404, "This room type is not available")
    return room_type


def rooms_left(db: Session, room_type: RoomType, check_in: date, check_out: date) -> int:
    booked = dict(db.query(RoomInventory.night, RoomInventory.booked).filter(
        RoomInventory.room_type_id == room_type.id, RoomInventory.night >= check_in,
        RoomInventory.night < check_out).all())
    return min(room_type.total_rooms - booked.get(n, 0) for n in nights_between(check_in, check_out))


def price(venue: Venue, room_type: RoomType, nights: int, rooms: int) -> dict:
    rate = Decimal(room_type.nightly_rate).quantize(CENT)
    subtotal = (rate * nights * rooms).quantize(CENT)
    taxes = (subtotal * Decimal(venue.tax_rate)).quantize(CENT, rounding=ROUND_HALF_UP)
    return {"nightly_rate": rate, "nights": nights, "rooms": rooms, "subtotal": subtotal,
            "tax_rate": Decimal(venue.tax_rate), "taxes": taxes, "total": subtotal + taxes,
            "currency": venue.currency}


def free_cancellation_until(venue: Venue, check_in: date) -> datetime:
    arrival = datetime.combine(check_in, venue.check_in_time or time(14, 0), tzinfo=venue_tz(venue))
    return arrival - timedelta(hours=venue.free_cancellation_hours)


def quote(db: Session, venue_id: str, room_type_id: str, check_in: date, check_out: date, guests: int,
          rooms: int = 1) -> dict:
    venue = get_active_venue(db, venue_id, VenueKind.HOTEL)
    room_type = _room_type(db, venue, room_type_id)
    validate_stay(venue, room_type, check_in, check_out, guests, rooms)
    left = rooms_left(db, room_type, check_in, check_out)
    return {**price(venue, room_type, (check_out - check_in).days, rooms), "room_type_id": room_type.id,
            "room_type_name": room_type.name, "check_in": check_in, "check_out": check_out, "guests": guests,
            "rooms_left": max(left, 0), "available": left >= rooms,
            "free_cancellation_until": free_cancellation_until(venue, check_in)}


def _reserve_nights(db: Session, room_type: RoomType, check_in: date, check_out: date, rooms: int) -> None:
    for night in nights_between(check_in, check_out):
        db.execute(insert(RoomInventory).values(room_type_id=room_type.id, night=night, booked=0)
                   .on_conflict_do_nothing())
        updated = db.execute(text(
            "UPDATE room_inventory SET booked = booked + :n WHERE room_type_id = :rt AND night = :night "
            "AND booked + :n <= :total RETURNING booked"),
            {"n": rooms, "rt": room_type.id, "night": night, "total": room_type.total_rooms}).first()
        if updated is None:
            db.rollback()
            raise conflict(f"{room_type.name} is sold out for the night of {night:%d %b %Y}. "
                           "Try other dates or another room type.")


def _release_nights(db: Session, room_type_id: str, nights: list[date], rooms: int) -> None:
    for night in nights:
        db.execute(text("UPDATE room_inventory SET booked = booked - :n WHERE room_type_id = :rt "
                        "AND night = :night AND booked >= :n"), {"n": rooms, "rt": room_type_id, "night": night})


def find_by_idempotency(db: Session, customer_id: str, key: Optional[str]) -> Optional[Reservation]:
    if not key:
        return None
    return db.query(Reservation).filter(Reservation.customer_id == customer_id,
                                        Reservation.idempotency_key == key).first()


def create_reservation(db: Session, customer: User, *, venue_id: str, room_type_id: str, check_in: date,
                       check_out: date, guests: int, rooms: int = 1, special_requests: Optional[str] = None,
                       idempotency_key: Optional[str] = None, source: str = "web") -> tuple[Reservation, bool]:
    existing = find_by_idempotency(db, customer.id, idempotency_key)
    if existing:
        return existing, False
    venue = get_active_venue(db, venue_id, VenueKind.HOTEL)
    room_type = _room_type(db, venue, room_type_id, lock=True)
    validate_stay(venue, room_type, check_in, check_out, guests, rooms)
    _reserve_nights(db, room_type, check_in, check_out, rooms)
    amounts = price(venue, room_type, (check_out - check_in).days, rooms)
    reservation = Reservation(
        reference=new_reference(VenueKind.HOTEL), customer_id=customer.id, venue_id=venue.id,
        room_type_id=room_type.id, check_in=check_in, check_out=check_out, guests=guests, rooms=rooms,
        nights=amounts["nights"], nightly_rate=amounts["nightly_rate"], subtotal=amounts["subtotal"],
        taxes=amounts["taxes"], total=amounts["total"], currency=venue.currency,
        status=ReservationStatus.CONFIRMED, special_requests=special_requests or None,
        idempotency_key=idempotency_key)
    db.add(reservation)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        repeated = find_by_idempotency(db, customer.id, idempotency_key)
        if repeated:
            return repeated, False
        raise
    audit.record(db, "reservation.created", actor_id=customer.id, entity_type="reservation",
                 entity_id=reservation.id, to_status="CONFIRMED", total=str(amounts["total"]), source=source)
    notify(db, customer.id, NotificationType.BOOKING_CONFIRMED,
           f"Reserved: {room_type.name} at {venue.name}, {check_in:%d %b} to {check_out:%d %b %Y} "
           f"({amounts['nights']} night{'s' if amounts['nights'] > 1 else ''}). Reference {reservation.reference}.",
           dedupe_key=f"res-confirmed:{reservation.id}", reservation_id=reservation.id)
    db.commit()
    db.refresh(reservation)
    return reservation, True


def _lock_own(db: Session, customer: User, reference: str) -> Reservation:
    reservation = (db.query(Reservation).filter(Reservation.reference == reference)
                   .populate_existing().with_for_update().first())
    if reservation is None or reservation.customer_id != customer.id:
        raise HTTPException(404, "Reservation not found")
    return reservation


def cancellation_terms(reservation: Reservation) -> dict:
    deadline = free_cancellation_until(reservation.venue, reservation.check_in)
    late = utcnow() > deadline
    fee = (Decimal(reservation.nightly_rate) * reservation.rooms).quantize(CENT) if late else Decimal("0.00")
    return {"free_cancellation_until": deadline, "late": late, "fee": fee, "currency": reservation.currency}


def cancel_reservation(db: Session, customer: User, reference: str, source: str = "web") -> Reservation:
    reservation = _lock_own(db, customer, reference)
    if reservation.status != ReservationStatus.CONFIRMED:
        raise conflict(f"A reservation that is {reservation.status.value.lower().replace('_', ' ')} "
                       "cannot be cancelled")
    if reservation.check_in < local_today(reservation.venue):
        raise conflict("This stay has already started; please contact the hotel")
    terms = cancellation_terms(reservation)
    db.query(RoomType).filter(RoomType.id == reservation.room_type_id).with_for_update().one()
    _release_nights(db, reservation.room_type_id, nights_between(reservation.check_in, reservation.check_out),
                    reservation.rooms)
    reservation.status = ReservationStatus.CANCELLED
    reservation.cancelled_at = utcnow()
    reservation.cancellation_fee = terms["fee"]
    audit.record(db, "reservation.status", actor_id=customer.id, entity_type="reservation",
                 entity_id=reservation.id, from_status="CONFIRMED", to_status="CANCELLED", fee=str(terms["fee"]),
                 source=source)
    fee_text = (f" A late-cancellation charge of {reservation.currency} {terms['fee']} is payable to the hotel."
                if terms["late"] else " No cancellation charge applies.")
    notify(db, customer.id, NotificationType.BOOKING_CANCELLED,
           f"Cancelled reservation {reservation.reference} at {reservation.venue.name}.{fee_text}",
           dedupe_key=f"res-cancelled:{reservation.id}", reservation_id=reservation.id)
    db.commit()
    db.refresh(reservation)
    return reservation


def modify_reservation(db: Session, customer: User, reference: str, *, check_in: date, check_out: date,
                       guests: int, room_type_id: Optional[str] = None) -> Reservation:
    reservation = _lock_own(db, customer, reference)
    if reservation.status != ReservationStatus.CONFIRMED:
        raise conflict("Only confirmed reservations can be changed")
    venue = get_active_venue(db, reservation.venue_id, VenueKind.HOTEL)
    if reservation.check_in <= local_today(venue):
        raise conflict("Changes are not possible on or after the check-in date; please contact the hotel")
    new_type_id = room_type_id or reservation.room_type_id
    locked = {rt_id: _room_type(db, venue, rt_id, lock=True) if rt_id == new_type_id else
              db.query(RoomType).filter(RoomType.id == rt_id).with_for_update().one()
              for rt_id in sorted({reservation.room_type_id, new_type_id})}
    new_type = locked[new_type_id]
    validate_stay(venue, new_type, check_in, check_out, guests, reservation.rooms)
    old = (reservation.room_type_id, reservation.check_in, reservation.check_out)
    # Release then reserve in one transaction: if the new stay does not fit,
    # the rollback restores the original reservation untouched.
    _release_nights(db, reservation.room_type_id, nights_between(reservation.check_in, reservation.check_out),
                    reservation.rooms)
    _reserve_nights(db, new_type, check_in, check_out, reservation.rooms)
    amounts = price(venue, new_type, (check_out - check_in).days, reservation.rooms)
    reservation.room_type_id, reservation.check_in, reservation.check_out = new_type.id, check_in, check_out
    reservation.guests = guests
    for key in ("nights", "nightly_rate", "subtotal", "taxes", "total"):
        setattr(reservation, key, amounts[key])
    audit.record(db, "reservation.modified", actor_id=customer.id, entity_type="reservation",
                 entity_id=reservation.id, old_room_type=old[0], old_check_in=str(old[1]), old_check_out=str(old[2]),
                 new_check_in=str(check_in), new_check_out=str(check_out), total=str(amounts["total"]))
    notify(db, customer.id, NotificationType.BOOKING_UPDATED,
           f"Updated reservation {reservation.reference}: {new_type.name}, {check_in:%d %b} to "
           f"{check_out:%d %b %Y}. New total {reservation.currency} {amounts['total']}.",
           reservation_id=reservation.id)
    db.commit()
    db.refresh(reservation)
    return reservation


STAFF_TRANSITIONS = {
    "check-in": (ReservationStatus.CONFIRMED, ReservationStatus.CHECKED_IN),
    "check-out": (ReservationStatus.CHECKED_IN, ReservationStatus.CHECKED_OUT),
    "no-show": (ReservationStatus.CONFIRMED, ReservationStatus.NO_SHOW),
}


def staff_transition(db: Session, user: User, reservation_id: str, action: str) -> Reservation:
    if action not in STAFF_TRANSITIONS:
        raise HTTPException(404, "Unknown action")
    reservation = db.query(Reservation).filter(Reservation.id == reservation_id).with_for_update().first()
    if reservation is None:
        raise HTTPException(404, "Reservation not found")
    require_operator(db, user, reservation.venue_id)
    source, target = STAFF_TRANSITIONS[action]
    if reservation.status != source:
        raise conflict(f"Cannot {action.replace('-', ' ')} a reservation that is "
                       f"{reservation.status.value.lower().replace('_', ' ')}")
    today = local_today(reservation.venue)
    if action in ("check-in", "no-show") and today < reservation.check_in:
        raise conflict("This stay has not started yet")
    if action == "no-show":
        remaining = [n for n in nights_between(reservation.check_in, reservation.check_out) if n >= today]
        db.query(RoomType).filter(RoomType.id == reservation.room_type_id).with_for_update().one()
        _release_nights(db, reservation.room_type_id, remaining, reservation.rooms)
    reservation.status = target
    audit.record(db, "reservation.status", actor_id=user.id, entity_type="reservation", entity_id=reservation.id,
                 from_status=source.value, to_status=target.value, source="staff")
    notify(db, reservation.customer_id, NotificationType.BOOKING_UPDATED,
           f"Reservation {reservation.reference} at {reservation.venue.name}: "
           f"{target.value.replace('_', ' ').lower()}.", dedupe_key=f"res-{action}:{reservation.id}",
           reservation_id=reservation.id)
    db.commit()
    db.refresh(reservation)
    return reservation
