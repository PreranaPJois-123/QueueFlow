from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

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
    service = db.get(Service, payload.service_id)
    if not service or not service.is_active:
        raise HTTPException(404, "Active service not found")
    if payload.scheduled_time.tzinfo is None or payload.scheduled_time <= datetime.now(timezone.utc):
        raise HTTPException(422, "Choose a future appointment time with a timezone")
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
    appt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
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
