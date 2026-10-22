from datetime import date, datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.models import Appointment, AppointmentStatus, Service, User
from app.schemas.schemas import AppointmentCreate, AppointmentOut

router = APIRouter(prefix="/api/appointments", tags=["appointments"])


@router.get("", response_model=list[AppointmentOut])
def list_my_appointments(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return (
        db.query(Appointment)
        .filter(Appointment.customer_id == current_user.id)
        .order_by(Appointment.scheduled_time.asc())
        .all()
    )


@router.post("", response_model=AppointmentOut, status_code=status.HTTP_201_CREATED)
def create_appointment(payload: AppointmentCreate, db: Session = Depends(get_db),
                        current_user: User = Depends(get_current_user)):
    # All booking writers lock customer then service, serializing overlapping reservations.
    db.query(User).filter(User.id == current_user.id).populate_existing().with_for_update().one()
    service = db.query(Service).filter(Service.id == payload.service_id).populate_existing().with_for_update().first()
    if not service or not service.is_active:
        raise HTTPException(404, "Active service not found")
    if payload.scheduled_time.tzinfo is None or payload.scheduled_time <= datetime.now(timezone.utc):
        raise HTTPException(422, "Choose a future appointment time with a timezone")
    if payload.scheduled_time > datetime.now(timezone.utc) + timedelta(days=90):
        raise HTTPException(422, "Appointments can be booked up to 90 days ahead")
    if booking_conflict(db, payload.service_id, current_user.id, payload.scheduled_time):
        raise HTTPException(409, "This time conflicts with an existing service or personal appointment. Choose another slot.")
    appt = Appointment(
        customer_id=current_user.id,
        service_id=payload.service_id,
        scheduled_time=payload.scheduled_time,
        notes=payload.notes,
    )
    db.add(appt)
    db.commit()
    db.refresh(appt)
    return appt


@router.post("/{appointment_id}/cancel", response_model=AppointmentOut)
def cancel_appointment(appointment_id: str, db: Session = Depends(get_db),
                        current_user: User = Depends(get_current_user)):
    appt = db.query(Appointment).filter(Appointment.id == appointment_id).populate_existing().with_for_update().first()
    if not appt:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Appointment not found")
    if appt.customer_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This is not your appointment")
    if appt.status != AppointmentStatus.SCHEDULED:
        raise HTTPException(409, "Only scheduled appointments can be cancelled")
    appt.status = AppointmentStatus.CANCELLED
    db.commit()
    db.refresh(appt)
    return appt


# A service admits one appointment at a time, with a 30-minute reservation.
# Continuous appointment hours preserve existing arbitrary-time API bookings.
SLOT_MINUTES = 30


def booking_conflict(db, service_id, customer_id, when):
    return db.query(Appointment.id).filter(
        Appointment.status.in_([AppointmentStatus.SCHEDULED, AppointmentStatus.CHECKED_IN]),
        or_(Appointment.service_id == service_id, Appointment.customer_id == customer_id),
        Appointment.scheduled_time > when - timedelta(minutes=SLOT_MINUTES),
        Appointment.scheduled_time < when + timedelta(minutes=SLOT_MINUTES),
    ).first() is not None


@router.get("/availability/{service_id}")
def availability(service_id: str, day: date, utc_offset_minutes: int = 0,
                 db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not -720 <= utc_offset_minutes <= 840:
        raise HTTPException(422, "Invalid timezone offset")
    service = db.get(Service, service_id)
    if not service or not service.is_active:
        raise HTTPException(404, "Active service not found")
    start = datetime.combine(day, datetime.min.time(), tzinfo=timezone(timedelta(minutes=utc_offset_minutes)))
    now = datetime.now(timezone.utc)
    if start + timedelta(days=1) <= now or start > now + timedelta(days=90):
        raise HTTPException(422, "Choose a date within the next 90 days")
    slots = []
    for index in range(48):
        when = (start + timedelta(minutes=index*SLOT_MINUTES)).astimezone(timezone.utc)
        if when > now and not booking_conflict(db, service_id, current_user.id, when):
            slots.append(when.isoformat())
    return {"slots": slots, "duration_minutes": SLOT_MINUTES}
