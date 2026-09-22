from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, extract
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_staff
from app.models.models import Queue, QueueStatus, Ticket, TicketStatus, ServiceRecord, User
from app.schemas.schemas import AnalyticsOut

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("", response_model=AnalyticsOut)
def get_analytics(db: Session = Depends(get_db), _: User = Depends(require_staff)):
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    served_today = (
        db.query(func.count(Ticket.id))
        .filter(Ticket.status == TicketStatus.SERVED, Ticket.served_at >= today_start)
        .scalar() or 0
    )
    skipped_today = (
        db.query(func.count(Ticket.id))
        .filter(Ticket.status == TicketStatus.SKIPPED, Ticket.skipped_at >= today_start)
        .scalar() or 0
    )
    active_queues = (
        db.query(func.count(Queue.id)).filter(Queue.status == QueueStatus.OPEN).scalar() or 0
    )
    avg_wait_seconds = db.query(func.avg(ServiceRecord.wait_seconds)).scalar() or 0
    avg_service_seconds = db.query(func.avg(ServiceRecord.service_seconds)).scalar() or 0

    busiest_hour_row = (
        db.query(extract("hour", Ticket.created_at).label("hour"), func.count(Ticket.id).label("cnt"))
        .group_by("hour")
        .order_by(func.count(Ticket.id).desc())
        .first()
    )
    busiest_hour = int(busiest_hour_row.hour) if busiest_hour_row else None

    return AnalyticsOut(
        customers_served_today=served_today,
        average_wait_minutes=round(avg_wait_seconds / 60, 1),
        average_service_minutes=round(avg_service_seconds / 60, 1),
        active_queues=active_queues,
        completed_tickets_today=served_today,
        skipped_tickets_today=skipped_today,
        busiest_hour=busiest_hour,
    )
