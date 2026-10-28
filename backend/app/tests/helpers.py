from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.models.venues import Offering, Provider, RoomType, Venue, VenueKind
from app.seed import seed
from app.tests.conftest import TestSessionLocal

IST = ZoneInfo("Asia/Kolkata")


def seeded() -> dict:
    with TestSessionLocal() as db:
        seed(db)
        db.commit()
        venues = {v.name: v.id for v in db.query(Venue).all()}
    return venues


def next_working_day(min_days: int = 1) -> date:
    day = datetime.now(IST).date() + timedelta(days=min_days)
    while day.weekday() == 6:  # seed schedules run Monday-Saturday
        day += timedelta(days=1)
    return day


def offering_id(venue_id: str, name: str) -> str:
    with TestSessionLocal() as db:
        return db.query(Offering.id).filter(Offering.venue_id == venue_id, Offering.name == name).scalar()


def provider_id(venue_id: str, name: str) -> str:
    with TestSessionLocal() as db:
        return db.query(Provider.id).filter(Provider.venue_id == venue_id, Provider.name == name).scalar()


def room_type_id(venue_id: str, name: str) -> str:
    with TestSessionLocal() as db:
        return db.query(RoomType.id).filter(RoomType.venue_id == venue_id, RoomType.name == name).scalar()


def first_slot(client, venue_id, offering, day, provider=None):
    params = {"offering_id": offering, "date": day.isoformat()}
    if provider:
        params["provider_id"] = provider
    slots = client.get(f"/api/venues/{venue_id}/slots", params=params).json()
    assert slots, "expected free slots"
    return slots


def at(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=IST).astimezone(timezone.utc)


__all__ = ["VenueKind"]
