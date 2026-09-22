from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_staff
from app.models.models import Queue, Ticket, TicketStatus, User
from app.schemas.schemas import QueueCreate, QueueOut, TicketOut, TicketDetailOut
from app.services import queue_service
from app.services.ws_manager import manager

router = APIRouter(prefix="/api/queues", tags=["queues"])


@router.get("", response_model=list[QueueOut])
def list_queues(service_id: str | None = None, db: Session = Depends(get_db)):
    q = db.query(Queue)
    if service_id:
        q = q.filter(Queue.service_id == service_id)
    return q.order_by(Queue.created_at.desc()).all()


@router.post("", response_model=QueueOut, status_code=status.HTTP_201_CREATED)
def create_queue(payload: QueueCreate, db: Session = Depends(get_db),
                  current_user: User = Depends(require_staff)):
    queue = Queue(service_id=payload.service_id, name=payload.name)
    db.add(queue)
    db.commit()
    db.refresh(queue)
    return queue


@router.get("/{queue_id}", response_model=QueueOut)
def get_queue(queue_id: str, db: Session = Depends(get_db)):
    queue = db.query(Queue).filter(Queue.id == queue_id).first()
    if not queue:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Queue not found")
    return queue


async def _broadcast_state(db: Session, queue: Queue):
    state = queue_service.build_queue_state(db, queue)
    await manager.broadcast(queue.id, {"event": "queue_state", "data": state})


@router.post("/{queue_id}/join", response_model=TicketDetailOut, status_code=status.HTTP_201_CREATED)
async def join_queue(queue_id: str, db: Session = Depends(get_db),
                      current_user: User = Depends(get_current_user)):
    ticket = queue_service.join_queue(db, queue_id, current_user)
    queue = db.query(Queue).filter(Queue.id == queue_id).first()
    people_ahead = queue_service.get_people_ahead(db, queue, ticket)
    wait = queue_service.estimate_wait_minutes(db, queue, people_ahead)

    await _broadcast_state(db, queue)

    current_label = None
    if queue.current_serving_number is not None:
        current_label = f"#{queue.current_serving_number}"

    return TicketDetailOut(
        ticket=ticket, people_ahead=people_ahead, estimated_wait_minutes=wait,
        current_serving_label=current_label, queue_status=queue.status,
        smart_alert=False,
    )


@router.websocket("/{queue_id}/ws")
async def queue_websocket(websocket: WebSocket, queue_id: str):
    await manager.connect(queue_id, websocket)
    try:
        while True:
            # Clients don't need to send anything; this just keeps the connection open
            # and lets us detect disconnects.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(queue_id, websocket)
