"""Staff operations for assigned venues: appointment queues and hotel front desk."""
from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from app.api.serializers import booking_out, reservation_out
from app.core.database import get_db
from app.core.deps import require_staff
from app.models.models import User, UserRole
from app.models.venues import Reservation, ReservationStatus, Venue, VenueStaff
from app.schemas.venues import QueueControl, VenueSummary
from app.services.booking import hotels, queue_ops
from app.services.booking.common import get_active_venue, local_today, require_operator

router = APIRouter(prefix="/api/ops", tags=["staff operations"])


@router.get("/venues", response_model=list[VenueSummary])
def my_venues(db: Session = Depends(get_db), user: User = Depends(require_staff)):
    query = db.query(Venue).filter(Venue.is_active.is_(True))
    if user.role != UserRole.ADMIN:
        query = query.join(VenueStaff, VenueStaff.venue_id == Venue.id).filter(VenueStaff.user_id == user.id)
    return query.order_by(Venue.kind, Venue.name).all()


@router.get("/venues/{venue_id}/queue")
def venue_queue(venue_id: str, day: Optional[date] = Query(default=None, alias="date"),
                db: Session = Depends(get_db), user: User = Depends(require_staff)):
    venue = get_active_venue(db, venue_id)
    day = day or local_today(venue)
    return {"venue": VenueSummary.model_validate(venue), "date": day,
            "providers": queue_ops.board(db, user, venue, day)}


@router.post("/bookings/{booking_id}/{action}")
def booking_action(booking_id: str, action: Literal["check-in", "start", "complete", "no-show", "cancel"],
                   db: Session = Depends(get_db), user: User = Depends(require_staff)):
    return booking_out(db, queue_ops.staff_transition(db, user, booking_id, action))


@router.post("/providers/{provider_id}/queue/{day}/next")
def start_next(provider_id: str, day: date, db: Session = Depends(get_db), user: User = Depends(require_staff)):
    return booking_out(db, queue_ops.call_next(db, user, provider_id, day))


@router.post("/providers/{provider_id}/queue/{day}")
def control_queue(provider_id: str, day: date, payload: QueueControl, db: Session = Depends(get_db),
                  user: User = Depends(require_staff)):
    queue_day = queue_ops.set_queue_state(db, user, provider_id, day, paused=payload.paused,
                                          delay_minutes=payload.delay_minutes)
    return {"status": queue_day.status.value, "delay_minutes": queue_day.delay_minutes}


@router.get("/venues/{venue_id}/reservations")
def venue_reservations(venue_id: str, day: Optional[date] = Query(default=None, alias="date"),
                       status: Optional[ReservationStatus] = None, db: Session = Depends(get_db),
                       user: User = Depends(require_staff)):
    venue = get_active_venue(db, venue_id)
    require_operator(db, user, venue.id)
    day = day or local_today(venue)
    query = (db.query(Reservation).options(joinedload(Reservation.customer), joinedload(Reservation.room_type))
             .filter(Reservation.venue_id == venue.id, Reservation.check_in <= day, Reservation.check_out >= day))
    if status:
        query = query.filter(Reservation.status == status)
    return {"date": day, "items": [{**reservation_out(r).model_dump(), "guest_name": r.customer.full_name}
                                   for r in query.order_by(Reservation.check_in).limit(200).all()]}


@router.post("/reservations/{reservation_id}/{action}")
def reservation_action(reservation_id: str, action: Literal["check-in", "check-out", "no-show"],
                       db: Session = Depends(get_db), user: User = Depends(require_staff)):
    return reservation_out(hotels.staff_transition(db, user, reservation_id, action))
