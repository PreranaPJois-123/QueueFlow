"""History-based duration predictor, isolated from the queue state machine.

With >=20 positive completed durations, k-nearest-neighbour regression uses
cyclical UTC hour and weekday features. With less data it uses the recent
mean, or configured cold-start duration. No accuracy claims are made.
"""
from datetime import datetime, timezone
from math import sin, cos, pi, sqrt, ceil
from statistics import mean, median
from app.core.config import settings
from app.models.models import ServiceRecord, TicketStatus


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def features(value):
    value = utc(value)
    hour = (value.hour + value.minute / 60) * 2 * pi / 24
    day = value.weekday() * 2 * pi / 7
    return (sin(hour), cos(hour), sin(day), cos(day))


def predict_duration(db, queue_id, at=None):
    rows = (db.query(ServiceRecord).filter(ServiceRecord.queue_id == queue_id,
            ServiceRecord.outcome == TicketStatus.SERVED, ServiceRecord.service_seconds > 0)
            .order_by(ServiceRecord.created_at.desc()).limit(200).all())
    if not rows:
        return dict(service_minutes=settings.DEFAULT_AVG_SERVICE_MINUTES,
                    source="calculated_default", sample_count=0)
    seconds = mean(r.service_seconds for r in rows[:50])
    source = "calculated_history"
    if len(rows) >= 20:
        target = features(at or datetime.now(timezone.utc))
        ordered = sorted(rows, key=lambda r: sum((a-b)**2 for a,b in zip(features(r.created_at), target)))
        nearest = ordered[:max(5, int(sqrt(len(rows))))]
        # Median suppresses outliers without training on fabricated observations.
        seconds = median(r.service_seconds for r in nearest)
        source = "ml_knn"
    return dict(service_minutes=round(max(1, seconds / 60), 1), source=source, sample_count=len(rows))


def predict_wait(db, queue, people_ahead):
    prediction = predict_duration(db, queue.id)
    return {**prediction, "wait_minutes": max(0, ceil(people_ahead * prediction["service_minutes"]))}
