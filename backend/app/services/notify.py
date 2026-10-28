"""Durable, de-duplicated in-app notifications with realtime push."""
from typing import Optional

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.models import Notification, NotificationType, gen_uuid
from app.services import realtime


def notify(db: Session, user_id: str, kind: NotificationType, message: str, *, dedupe_key: Optional[str] = None,
           booking_id: Optional[str] = None, reservation_id: Optional[str] = None) -> bool:
    """Insert a notification unless one with the same dedupe key exists.

    Returns True when a new notification was created. The insert uses
    ON CONFLICT DO NOTHING, so concurrent producers (e.g. two instances of the
    queue monitor) cannot create duplicates.
    """
    values = dict(id=gen_uuid(), user_id=user_id, type=kind, message=message[:500], dedupe_key=dedupe_key,
                  booking_id=booking_id, reservation_id=reservation_id, is_read=False)
    stmt = insert(Notification).values(**values)
    if dedupe_key:
        stmt = stmt.on_conflict_do_nothing(index_elements=["dedupe_key"])
    created = db.execute(stmt.returning(Notification.id, Notification.created_at)).first()
    if created is None:
        return False
    realtime.enqueue(db, f"user:{user_id}", {"type": "notification", "data": {
        "id": created.id, "type": kind.value, "message": values["message"], "booking_id": booking_id,
        "reservation_id": reservation_id, "is_read": False, "created_at": created.created_at,
    }})
    return True
