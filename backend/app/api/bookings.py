"""Customer appointments (hospital/shop) and hotel reservations.

Every query is scoped to the signed-in user; references belonging to other
users return 404 so they cannot be probed. Clients may send an
``Idempotency-Key`` header so a retried request never creates a second booking.
"""
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Header, Query, Response, status
from sqlalchemy.orm import Session

from app.api.serializers import booking_out, reservation_out
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.rate_limit import rate_limit
from app.models.models import User
from app.models.venues import ACTIVE_BOOKING_STATUSES, Booking, Reservation, ReservationStatus
from app.schemas.venues import (
    BookingCreate, BookingOut, BookingReschedule, ReservationCreate, ReservationModify, ReservationOut,
)
from app.services.booking import appointments, hotels
from app.services.booking.common import utcnow
from fastapi import HTTPException

router = APIRouter(prefix="/api", tags=["bookings"])
IdempotencyKey = Header(default=None, alias="Idempotency-Key", max_length=64, pattern=r"^[A-Za-z0-9_\-]{8,64}$")


@router.post("/bookings", response_model=BookingOut, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(rate_limit)])
def create_booking(payload: BookingCreate, response: Response, idempotency_key: Optional[str] = IdempotencyKey,
                   db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    booking, created = appointments.create_booking(db, user, **payload.model_dump(),
                                                   idempotency_key=idempotency_key)
    if not created:
        response.status_code = status.HTTP_200_OK
    return booking_out(db, booking, live=True)


@router.get("/bookings", response_model=list[BookingOut])
def my_bookings(scope: Literal["upcoming", "past", "all"] = "upcoming", limit: int = Query(50, ge=1, le=100),
                db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    query = db.query(Booking).filter(Booking.customer_id == user.id)
    now = utcnow()
    if scope == "upcoming":
        query = query.filter(Booking.status.in_(ACTIVE_BOOKING_STATUSES), Booking.end_at >= now) \
            .order_by(Booking.start_at)
    elif scope == "past":
        query = query.filter((~Booking.status.in_(ACTIVE_BOOKING_STATUSES)) | (Booking.end_at < now)) \
            .order_by(Booking.start_at.desc())
    else:
        query = query.order_by(Booking.start_at.desc())
    return [booking_out(db, b, live=(scope == "upcoming")) for b in query.limit(limit).all()]


def _own_booking(db: Session, user: User, reference: str) -> Booking:
    booking = db.query(Booking).filter(Booking.reference == reference).first()
    if booking is None or booking.customer_id != user.id:
        raise HTTPException(404, "Booking not found")
    return booking


@router.get("/bookings/{reference}", response_model=BookingOut)
def booking_detail(reference: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return booking_out(db, _own_booking(db, user, reference), live=True)


@router.post("/bookings/{reference}/cancel", response_model=BookingOut)
def cancel_booking(reference: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return booking_out(db, appointments.cancel_booking(db, user, reference))


@router.post("/bookings/{reference}/reschedule", response_model=BookingOut)
def reschedule_booking(reference: str, payload: BookingReschedule, db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)):
    booking = appointments.reschedule_booking(db, user, reference, payload.start_at, payload.provider_id)
    return booking_out(db, booking, live=True)


@router.post("/reservations", response_model=ReservationOut, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(rate_limit)])
def create_reservation(payload: ReservationCreate, response: Response,
                       idempotency_key: Optional[str] = IdempotencyKey, db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)):
    reservation, created = hotels.create_reservation(db, user, **payload.model_dump(),
                                                     idempotency_key=idempotency_key)
    if not created:
        response.status_code = status.HTTP_200_OK
    return reservation_out(reservation)


@router.get("/reservations", response_model=list[ReservationOut])
def my_reservations(scope: Literal["upcoming", "past", "all"] = "upcoming", limit: int = Query(50, ge=1, le=100),
                    db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    query = db.query(Reservation).filter(Reservation.customer_id == user.id)
    today = utcnow().date()
    active = [ReservationStatus.CONFIRMED, ReservationStatus.CHECKED_IN]
    if scope == "upcoming":
        query = query.filter(Reservation.status.in_(active), Reservation.check_out >= today) \
            .order_by(Reservation.check_in)
    elif scope == "past":
        query = query.filter((~Reservation.status.in_(active)) | (Reservation.check_out < today)) \
            .order_by(Reservation.check_in.desc())
    else:
        query = query.order_by(Reservation.check_in.desc())
    return [reservation_out(r) for r in query.limit(limit).all()]


def _own_reservation(db: Session, user: User, reference: str) -> Reservation:
    reservation = db.query(Reservation).filter(Reservation.reference == reference).first()
    if reservation is None or reservation.customer_id != user.id:
        raise HTTPException(404, "Reservation not found")
    return reservation


@router.get("/reservations/{reference}", response_model=ReservationOut)
def reservation_detail(reference: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return reservation_out(_own_reservation(db, user, reference))


@router.get("/reservations/{reference}/cancellation-terms")
def reservation_cancellation_terms(reference: str, db: Session = Depends(get_db),
                                   user: User = Depends(get_current_user)):
    return hotels.cancellation_terms(_own_reservation(db, user, reference))


@router.post("/reservations/{reference}/cancel", response_model=ReservationOut)
def cancel_reservation(reference: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return reservation_out(hotels.cancel_reservation(db, user, reference))


@router.post("/reservations/{reference}/modify", response_model=ReservationOut)
def modify_reservation(reference: str, payload: ReservationModify, db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)):
    return reservation_out(hotels.modify_reservation(db, user, reference, **payload.model_dump()))
