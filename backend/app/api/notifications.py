"""In-app notifications and the authenticated per-user realtime socket."""
import asyncio
import time

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.database import SessionLocal, get_db
from app.core.deps import get_current_user
from app.core.sessions import resolve_session
from app.models.models import Notification, User
from app.services import realtime

router = APIRouter(prefix="/api", tags=["notifications"])


def _out(n: Notification) -> dict:
    return {"id": n.id, "type": n.type.value, "message": n.message, "booking_id": n.booking_id,
            "reservation_id": n.reservation_id, "is_read": n.is_read, "created_at": n.created_at}


@router.get("/notifications")
def list_notifications(unread_only: bool = False, limit: int = Query(30, ge=1, le=100),
                       offset: int = Query(0, ge=0), db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)):
    query = db.query(Notification).filter(Notification.user_id == user.id)
    unread = query.filter(Notification.is_read.is_(False)).count()
    if unread_only:
        query = query.filter(Notification.is_read.is_(False))
    items = query.order_by(Notification.created_at.desc()).offset(offset).limit(limit).all()
    return {"items": [_out(n) for n in items], "unread": unread}


@router.post("/notifications/{notification_id}/read")
def mark_read(notification_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    updated = db.query(Notification).filter(Notification.id == notification_id,
                                            Notification.user_id == user.id).update({"is_read": True})
    if not updated:
        raise HTTPException(404, "Notification not found")
    db.commit()
    return {"ok": True}


@router.post("/notifications/read-all")
def mark_all_read(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    count = db.query(Notification).filter(Notification.user_id == user.id,
                                          Notification.is_read.is_(False)).update({"is_read": True})
    db.commit()
    return {"updated": count}


def _authenticate(token: str | None) -> str | None:
    with SessionLocal() as db:
        session = resolve_session(db, token)
        if session is None:
            return None
        user = db.get(User, session.user_id)
        return user.id if user and user.is_active else None


@router.websocket("/ws")
async def user_socket(websocket: WebSocket):
    """Private event stream for the signed-in user (session cookie required).

    The session is re-validated every 30 seconds, so logging out or a password
    change closes open sockets. Clients may only send short "ping" frames.
    """
    origin = websocket.headers.get("origin")
    if origin and origin not in settings.cors_origins_list:
        await websocket.close(code=1008)
        return
    token = websocket.cookies.get(settings.SESSION_COOKIE_NAME)
    user_id = await run_in_threadpool(_authenticate, token)
    if user_id is None:
        await websocket.close(code=4401)
        return
    channel = f"user:{user_id}"
    if realtime.hub.count(channel) >= settings.MAX_WS_PER_USER:
        await websocket.close(code=4429)
        return
    await websocket.accept()
    realtime.hub.add(channel, websocket)
    try:
        await websocket.send_json({"type": "hello"})
        last_check = time.monotonic()
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive_text(), timeout=30)
            except asyncio.TimeoutError:
                message = None
            if message is not None and (len(message) > 64 or message != "ping"):
                await websocket.close(code=1003)
                return
            if time.monotonic() - last_check >= 30:
                last_check = time.monotonic()
                if await run_in_threadpool(_authenticate, token) != user_id:
                    await websocket.close(code=4401)
                    return
            if message == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        realtime.hub.remove(channel, websocket)
