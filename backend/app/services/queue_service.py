"""
Core queue state-machine logic.

Concurrency strategy:
  Every mutating operation (join, call_next, skip, serve, cancel) takes a
  `SELECT ... FOR UPDATE` row lock on the Queue row first. Postgres will
  block a second concurrent transaction on the same queue until the first
  commits, so two staff members clicking "Call Next" at the same instant
  cannot both advance the counter / grab the same ticket. This is the
  standard, explainable way to serialize access to a shared counter
  without introducing a separate lock service.
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.models import (
    Queue, Ticket, TicketStatus, QueueStatus, ServiceRecord, User, Notification, NotificationType,
)


def _label(number: int) -> str:
    """Token label like A001, A002, ... A999, then B001..."""
    letter_index, seq = divmod(number - 1, 999)
    letter = chr(ord("A") + letter_index)
    return f"{letter}{seq + 1:03d}"


def get_average_service_seconds(db: Session, queue_id: str) -> int:
    """Average of the last 50 completed service durations for this queue.
    Falls back to a configured default when there's no history yet."""
    recent_subq = (
        db.query(ServiceRecord.service_seconds)
        .filter(ServiceRecord.queue_id == queue_id)
        .order_by(ServiceRecord.created_at.desc())
        .limit(50)
        .subquery()
    )
    avg = db.query(func.avg(recent_subq.c.service_seconds)).scalar()
    if avg is None:
        return settings.DEFAULT_AVG_SERVICE_MINUTES * 60
    return int(avg)


def _to_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def get_people_ahead(db: Session, queue: Queue, ticket: Ticket) -> int:
    if ticket.status not in (TicketStatus.WAITING, TicketStatus.CALLED):
        return 0
    return (
        db.query(Ticket)
        .filter(
            Ticket.queue_id == queue.id,
            Ticket.status.in_([TicketStatus.WAITING, TicketStatus.CALLED]),
            Ticket.token_number < ticket.token_number,
        )
        .count()
    )


def estimate_wait_minutes(db: Session, queue: Queue, people_ahead: int) -> int:
    avg_seconds = get_average_service_seconds(db, queue.id)
    return max(0, round((people_ahead * avg_seconds) / 60))


def _lock_queue(db: Session, queue_id: str) -> Queue:
    queue = db.query(Queue).filter(Queue.id == queue_id).with_for_update().first()
    if queue is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Queue not found")
    return queue


def join_queue(db: Session, queue_id: str, customer: User) -> Ticket:
    queue = _lock_queue(db, queue_id)

    if queue.status != QueueStatus.OPEN:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Queue is {queue.status.value.lower()} and not accepting new tickets")

    existing = (
        db.query(Ticket)
        .filter(
            Ticket.queue_id == queue_id,
            Ticket.customer_id == customer.id,
            Ticket.status.in_([TicketStatus.WAITING, TicketStatus.CALLED, TicketStatus.SERVING]),
        )
        .first()
    )
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "You already have an active ticket in this queue")

    token_number = queue.next_token_number
    queue.next_token_number = token_number + 1

    ticket = Ticket(
        queue_id=queue.id,
        customer_id=customer.id,
        token_number=token_number,
        token_label=_label(token_number),
        status=TicketStatus.WAITING,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


def call_next(db: Session, queue_id: str) -> Optional[Ticket]:
    queue = _lock_queue(db, queue_id)

    if queue.status != QueueStatus.OPEN:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Cannot call next: queue is {queue.status.value.lower()}")

    # Close out anyone currently mid-service? No — staff must explicitly "Serve"/"Skip" first.
    still_serving = (
        db.query(Ticket)
        .filter(Ticket.queue_id == queue_id, Ticket.status == TicketStatus.CALLED)
        .first()
    )
    if still_serving:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "A ticket is already called and awaiting check-in. Serve or skip it before calling next.",
        )

    next_ticket = (
        db.query(Ticket)
        .filter(Ticket.queue_id == queue_id, Ticket.status == TicketStatus.WAITING)
        .order_by(Ticket.created_at.asc())
        .first()
    )
    if next_ticket is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Queue is empty — no waiting tickets to call")

    next_ticket.status = TicketStatus.CALLED
    next_ticket.called_at = datetime.now(timezone.utc)
    queue.current_serving_number = next_ticket.token_number

    db.add(Notification(
        user_id=next_ticket.customer_id,
        ticket_id=next_ticket.id,
        type=NotificationType.CALLED,
        message=f"You're being called! Please proceed — your token is {next_ticket.token_label}.",
    ))

    db.commit()
    db.refresh(next_ticket)
    return next_ticket


def start_serving(db: Session, ticket_id: str) -> Ticket:
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).with_for_update().first()
    if ticket is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found")
    if ticket.status != TicketStatus.CALLED:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Cannot start serving a ticket in status {ticket.status.value}")

    ticket.status = TicketStatus.SERVING
    ticket.serving_started_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(ticket)
    return ticket


def serve_ticket(db: Session, ticket_id: str) -> Ticket:
    """Mark a ticket fully served and record the service duration for wait-time estimation."""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).with_for_update().first()
    if ticket is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found")
    if ticket.status not in (TicketStatus.CALLED, TicketStatus.SERVING):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Cannot serve a ticket in status {ticket.status.value}")

    now = datetime.now(timezone.utc)
    if ticket.serving_started_at is None:
        ticket.serving_started_at = now
    ticket.status = TicketStatus.SERVED
    ticket.served_at = now

    start_time = _to_utc(ticket.serving_started_at) or now
    create_time = _to_utc(ticket.created_at) or now
    wait_seconds = int((start_time - create_time).total_seconds())
    service_seconds = int((now - start_time).total_seconds())

    db.add(ServiceRecord(
        ticket_id=ticket.id,
        queue_id=ticket.queue_id,
        service_id=db.query(Queue.service_id).filter(Queue.id == ticket.queue_id).scalar(),
        wait_seconds=max(0, wait_seconds),
        service_seconds=max(0, service_seconds),
        outcome=TicketStatus.SERVED,
    ))

    queue = db.query(Queue).filter(Queue.id == ticket.queue_id).with_for_update().first()
    if queue and queue.current_serving_number == ticket.token_number:
        queue.current_serving_number = None

    db.commit()
    db.refresh(ticket)
    return ticket


def skip_ticket(db: Session, ticket_id: str) -> Ticket:
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).with_for_update().first()
    if ticket is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found")
    if ticket.status not in (TicketStatus.WAITING, TicketStatus.CALLED):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Cannot skip a ticket in status {ticket.status.value}")

    ticket.status = TicketStatus.SKIPPED
    ticket.skipped_at = datetime.now(timezone.utc)

    queue = db.query(Queue).filter(Queue.id == ticket.queue_id).with_for_update().first()
    if queue and queue.current_serving_number == ticket.token_number:
        queue.current_serving_number = None

    db.commit()
    db.refresh(ticket)
    return ticket


def cancel_ticket(db: Session, ticket_id: str, customer_id: str) -> Ticket:
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).with_for_update().first()
    if ticket is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found")
    if ticket.customer_id != customer_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This is not your ticket")
    if ticket.status not in (TicketStatus.WAITING,):
        raise HTTPException(status.HTTP_409_CONFLICT, "Only a waiting ticket can be cancelled")

    ticket.status = TicketStatus.CANCELLED
    ticket.cancelled_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(ticket)
    return ticket


def pause_queue(db: Session, queue_id: str) -> Queue:
    queue = _lock_queue(db, queue_id)
    if queue.status == QueueStatus.CLOSED:
        raise HTTPException(status.HTTP_409_CONFLICT, "Cannot pause a closed queue")
    queue.status = QueueStatus.PAUSED
    db.commit()
    db.refresh(queue)
    return queue


def resume_queue(db: Session, queue_id: str) -> Queue:
    queue = _lock_queue(db, queue_id)
    if queue.status != QueueStatus.PAUSED:
        raise HTTPException(status.HTTP_409_CONFLICT, "Only a paused queue can be resumed")
    queue.status = QueueStatus.OPEN
    db.commit()
    db.refresh(queue)
    return queue


def close_queue(db: Session, queue_id: str) -> Queue:
    queue = _lock_queue(db, queue_id)
    queue.status = QueueStatus.CLOSED
    db.commit()
    db.refresh(queue)
    return queue


def build_queue_state(db: Session, queue: Queue) -> dict:
    waiting = (
        db.query(Ticket)
        .filter(Ticket.queue_id == queue.id, Ticket.status == TicketStatus.WAITING)
        .order_by(Ticket.created_at.asc())
        .all()
    )
    called = (
        db.query(Ticket)
        .filter(Ticket.queue_id == queue.id, Ticket.status == TicketStatus.CALLED)
        .first()
    )
    current_label = None
    if queue.current_serving_number is not None:
        current_label = _label(queue.current_serving_number)

    return {
        "queue_id": queue.id,
        "queue_name": queue.name,
        "status": queue.status.value,
        "current_serving_label": current_label,
        "now_serving_ticket_id": called.id if called else None,
        "next_ticket_label": waiting[0].token_label if waiting else None,
        "waiting_labels": [t.token_label for t in waiting],
        "waiting_count": len(waiting),
    }
