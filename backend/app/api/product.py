"""Product read models: real aggregates with no private data in public snapshots."""
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload
from app.core.database import get_db
from app.core.deps import get_current_user, require_staff
from app.models.models import User, UserRole, Queue, Ticket, TicketStatus, Appointment, AppointmentStatus, Notification, ServiceRecord
from app.schemas.schemas import QueueOut, TicketOut, AppointmentOut, UserOut, NotificationOut
from app.services.queue_service import build_queue_state
from app.services.prediction import predict_duration, predict_wait, utc

router = APIRouter(prefix="/api/product", tags=["product"])
ACTIVE = [TicketStatus.WAITING, TicketStatus.CALLED, TicketStatus.SERVING]


def ticket_row(ticket):
    return {**TicketOut.model_validate(ticket).model_dump(), "queue_name": ticket.queue.name,
            "service_name": ticket.queue.service.name}


def appointment_row(appointment):
    return {**AppointmentOut.model_validate(appointment).model_dump(), "service_name": appointment.service.name}


@router.get("/queues")
def queues(db: Session = Depends(get_db)):
    result = []
    for queue in db.query(Queue).options(joinedload(Queue.service)).order_by(Queue.created_at.desc()).all():
        state = build_queue_state(db, queue)
        ahead = state["waiting_count"] + int(state["now_serving_ticket_id"] is not None)
        prediction = predict_wait(db, queue, ahead)
        result.append({**QueueOut.model_validate(queue).model_dump(), **state,
                       "service_name": queue.service.name, "service_active": queue.service.is_active,
                       "estimated_wait_minutes": prediction["wait_minutes"],
                       "estimated_service_minutes": prediction["service_minutes"],
                       "prediction_source": prediction["source"], "prediction_samples": prediction["sample_count"]})
    return result


@router.get("/mine")
def mine(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    tickets = db.query(Ticket).options(joinedload(Ticket.queue).joinedload(Queue.service)).filter(Ticket.customer_id == user.id).order_by(Ticket.created_at.desc()).all()
    appointments = db.query(Appointment).options(joinedload(Appointment.service)).filter(Appointment.customer_id == user.id).order_by(Appointment.scheduled_time).all()
    notifications = db.query(Notification).filter(Notification.user_id == user.id).order_by(Notification.created_at.desc()).limit(30).all()
    return {"tickets": [ticket_row(t) for t in tickets], "appointments": [appointment_row(a) for a in appointments],
            "notifications": [NotificationOut.model_validate(n).model_dump() for n in notifications]}


@router.post("/notifications/{notification_id}/read")
def read_notification(notification_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    notification = db.query(Notification).filter(Notification.id == notification_id, Notification.user_id == user.id).first()
    if not notification:
        raise HTTPException(404, "Notification not found")
    notification.is_read = True
    db.commit()
    return {"is_read": True}


@router.get("/customers")
def customers(db: Session = Depends(get_db), _: User = Depends(require_staff)):
    result = []
    users = db.query(User).filter(User.role == UserRole.CUSTOMER).order_by(User.full_name).all()
    for user in users:
        result.append({**UserOut.model_validate(user).model_dump(),
            "tickets": [ticket_row(t) for t in sorted(user.tickets, key=lambda t: utc(t.created_at), reverse=True)],
            "appointments": [appointment_row(a) for a in sorted(user.appointments, key=lambda a: utc(a.scheduled_time), reverse=True)]})
    return result


@router.get("/queues/{queue_id}/tickets")
def queue_tickets(queue_id: str, db: Session = Depends(get_db), _: User = Depends(require_staff)):
    if not db.get(Queue, queue_id):
        raise HTTPException(404, "Queue not found")
    tickets = db.query(Ticket).options(joinedload(Ticket.customer), joinedload(Ticket.queue).joinedload(Queue.service)).filter(Ticket.queue_id == queue_id, Ticket.status.in_(ACTIVE)).order_by(Ticket.token_number).all()
    return [{**ticket_row(t), "customer_name": t.customer.full_name, "customer_email": t.customer.email,
             "waiting_minutes": round(max(0, (datetime.now(timezone.utc)-utc(t.created_at)).total_seconds()/60), 1)} for t in tickets]


@router.get("/trends")
def trends(db: Session = Depends(get_db), _: User = Depends(require_staff)):
    now = datetime.now(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=6)
    daily = []
    for index in range(7):
        day = start + timedelta(days=index)
        end = day + timedelta(days=1)
        created = db.query(Ticket).filter(Ticket.created_at >= day, Ticket.created_at < end).count()
        served = db.query(Ticket).filter(Ticket.served_at >= day, Ticket.served_at < end).count()
        skipped = db.query(Ticket).filter(Ticket.skipped_at >= day, Ticket.skipped_at < end).count()
        daily.append({"date": day.date().isoformat(), "tickets": created, "served": served, "skipped": skipped})
    total = db.query(Ticket).count()
    served = db.query(Ticket).filter(Ticket.status == TicketStatus.SERVED).count()
    skipped = db.query(Ticket).filter(Ticket.status == TicketStatus.SKIPPED).count()
    return {"daily": daily, "total_tickets": total, "total_served": served,
            "completion_rate": round(served/total*100, 1) if total else 0,
            "skip_rate": round(skipped/total*100, 1) if total else 0,
            "waiting": db.query(Ticket).filter(Ticket.status == TicketStatus.WAITING).count(),
            "serving": db.query(Ticket).filter(Ticket.status.in_([TicketStatus.CALLED, TicketStatus.SERVING])).count(),
            "appointments": db.query(Appointment).count(),
            "active_appointments": db.query(Appointment).filter(Appointment.status.in_([AppointmentStatus.SCHEDULED, AppointmentStatus.CHECKED_IN]), Appointment.scheduled_time >= now.replace(hour=0, minute=0, second=0, microsecond=0)).count()}
