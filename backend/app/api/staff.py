from starlette.concurrency import run_in_threadpool
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_staff
from app.models.models import Queue, Ticket, TicketStatus, User
from app.schemas.schemas import TicketOut, QueueStateOut, QueueOut
from app.services import queue_service
from app.services.ws_manager import manager

router = APIRouter(prefix="/api/staff", tags=["staff"])


async def _broadcast(db: Session, queue_id: str):
    queue = db.query(Queue).filter(Queue.id == queue_id).first()
    state = queue_service.build_queue_state(db, queue)
    await manager.broadcast(queue_id, {"event": "queue_state", "data": state})
    return state


@router.get("/queues/{queue_id}/state", response_model=QueueStateOut)
def queue_state(queue_id: str, db: Session = Depends(get_db), _: User = Depends(require_staff)):
    queue = db.query(Queue).filter(Queue.id == queue_id).first()
    return queue_service.build_queue_state(db, queue)


@router.get("/queues/{queue_id}/waiting", response_model=list[TicketOut])
def waiting_tickets(queue_id: str, db: Session = Depends(get_db), _: User = Depends(require_staff)):
    queue_service.build_queue_state(db, db.get(Queue, queue_id))
    return (
        db.query(Ticket)
        .filter(Ticket.queue_id == queue_id, Ticket.status == TicketStatus.WAITING)
        .order_by(Ticket.token_number.asc())
        .all()
    )


@router.post("/queues/{queue_id}/next", response_model=TicketOut)
async def call_next(queue_id: str, db: Session = Depends(get_db), _: User = Depends(require_staff)):
    ticket = await run_in_threadpool(queue_service.call_next, db, queue_id)
    await _broadcast(db, queue_id)
    return ticket


@router.post("/queues/{queue_id}/pause", response_model=QueueOut)
async def pause_queue(queue_id: str, db: Session = Depends(get_db), _: User = Depends(require_staff)):
    queue = await run_in_threadpool(queue_service.pause_queue, db, queue_id)
    await _broadcast(db, queue_id)
    return queue


@router.post("/queues/{queue_id}/resume", response_model=QueueOut)
async def resume_queue(queue_id: str, db: Session = Depends(get_db), _: User = Depends(require_staff)):
    queue = await run_in_threadpool(queue_service.resume_queue, db, queue_id)
    await _broadcast(db, queue_id)
    return queue


@router.post("/queues/{queue_id}/close", response_model=QueueOut)
async def close_queue(queue_id: str, db: Session = Depends(get_db), _: User = Depends(require_staff)):
    queue = await run_in_threadpool(queue_service.close_queue, db, queue_id)
    await _broadcast(db, queue_id)
    return queue


@router.post("/tickets/{ticket_id}/serve", response_model=TicketOut)
async def serve_ticket(ticket_id: str, db: Session = Depends(get_db), _: User = Depends(require_staff)):
    ticket = await run_in_threadpool(queue_service.serve_ticket, db, ticket_id)
    await _broadcast(db, ticket.queue_id)
    return ticket


@router.post("/tickets/{ticket_id}/skip", response_model=TicketOut)
async def skip_ticket(ticket_id: str, db: Session = Depends(get_db), _: User = Depends(require_staff)):
    ticket = await run_in_threadpool(queue_service.skip_ticket, db, ticket_id)
    await _broadcast(db, ticket.queue_id)
    return ticket
