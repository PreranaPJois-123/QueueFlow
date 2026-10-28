from typing import Any, Optional

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.models import AuditEvent


def record(db: Session, action: str, *, actor_id: Optional[str] = None, entity_type: Optional[str] = None,
           entity_id: Optional[str] = None, request: Optional[Request] = None, **detail: Any) -> None:
    """Add an audit event to the current transaction (the caller commits)."""
    db.add(AuditEvent(
        actor_id=actor_id, action=action, entity_type=entity_type, entity_id=entity_id,
        detail={k: (str(v) if not isinstance(v, (int, float, bool, type(None), list, dict)) else v)
                for k, v in detail.items()},
        ip_address=(request.client.host if request is not None and request.client else None),
    ))
