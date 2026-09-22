from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import settings
from app.core.deps import get_current_user
from app.models.models import Ticket, Queue, TicketStatus, User
from app.schemas.schemas import TicketOut, TicketDetailOut
from app.services import queue_service
from app.services.ws_manager import manager

router = APIRouter(prefix="/api/tickets", tags=["tickets"])


@router.get("/mine", response_model=list[TicketOut])
def my_tickets(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return (
        db.query(Ticket)
        .filter(Ticket.customer_id == current_user.id)
        .order_by(Ticket.created_at.desc())
        .all()
    )


@router.get("/{ticket_id}", response_model=TicketDetailOut)
def get_ticket(ticket_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found")
    if ticket.customer_id != current_user.id and current_user.role.value == "CUSTOMER":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This is not your ticket")

    queue = db.query(Queue).filter(Queue.id == ticket.queue_id).first()
    people_ahead = queue_service.get_people_ahead(db, queue, ticket)
    wait = queue_service.estimate_wait_minutes(db, queue, people_ahead)
    current_label = f"#{queue.current_serving_number}" if queue.current_serving_number is not None else None

    return TicketDetailOut(
        ticket=ticket,
        people_ahead=people_ahead,
        estimated_wait_minutes=wait,
        current_serving_label=current_label,
        queue_status=queue.status,
        smart_alert=(ticket.status == TicketStatus.WAITING and people_ahead <= settings.SMART_ALERT_THRESHOLD),
    )


@router.post("/{ticket_id}/cancel", response_model=TicketOut)
async def cancel_ticket(ticket_id: str, db: Session = Depends(get_db),
                         current_user: User = Depends(get_current_user)):
    ticket = queue_service.cancel_ticket(db, ticket_id, current_user.id)
    queue = db.query(Queue).filter(Queue.id == ticket.queue_id).first()
    state = queue_service.build_queue_state(db, queue)
    await manager.broadcast(queue.id, {"event": "queue_state", "data": state})
    return ticket
