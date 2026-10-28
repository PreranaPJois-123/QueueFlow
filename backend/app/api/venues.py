"""Public catalogue: hospitals, shops and hotels, slots and hotel quotes."""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, selectinload

from app.api.serializers import venue_detail
from app.core.database import get_db
from app.core.rate_limit import rate_limit
from app.models.venues import Offering, Provider, RoomType, Specialization, Venue, VenueKind
from app.schemas.venues import Page, QuoteOut, SlotOut, SpecializationOut, VenueDetail, VenueSummary
from app.services.booking import hotels
from app.services.booking.common import get_active_venue
from app.services.booking.slots import authorised_providers, available_slots

router = APIRouter(prefix="/api", tags=["catalogue"])


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.get("/venues", response_model=Page[VenueSummary])
def list_venues(kind: Optional[VenueKind] = None, q: Optional[str] = Query(default=None, max_length=80),
                city: Optional[str] = Query(default=None, max_length=80),
                specialization: Optional[str] = Query(default=None, max_length=90),
                limit: int = Query(default=20, ge=1, le=50), offset: int = Query(default=0, ge=0, le=10000),
                db: Session = Depends(get_db)):
    query = db.query(Venue).filter(Venue.is_active.is_(True))
    if kind:
        query = query.filter(Venue.kind == kind)
    if q and q.strip():
        pattern = f"%{_escape_like(q.strip())}%"
        query = query.filter(or_(Venue.name.ilike(pattern, escape="\\"), Venue.city.ilike(pattern, escape="\\"),
                                 Venue.address.ilike(pattern, escape="\\"),
                                 Venue.category.ilike(pattern, escape="\\")))
    if city and city.strip():
        query = query.filter(func.lower(Venue.city) == city.strip().lower())
    if specialization:
        query = query.filter(Venue.offerings.any(
            (Offering.is_active.is_(True)) & Offering.specialization.has(Specialization.slug == specialization)))
    total = query.count()
    items = query.order_by(Venue.name).offset(offset).limit(limit).all()
    return Page(items=[VenueSummary.model_validate(v) for v in items], total=total, limit=limit, offset=offset)


@router.get("/venues/cities", response_model=list[str])
def list_cities(kind: Optional[VenueKind] = None, db: Session = Depends(get_db)):
    query = db.query(Venue.city).filter(Venue.is_active.is_(True))
    if kind:
        query = query.filter(Venue.kind == kind)
    return [c for (c,) in query.distinct().order_by(Venue.city).all()]


@router.get("/specializations", response_model=list[SpecializationOut])
def list_specializations(db: Session = Depends(get_db)):
    """Specializations offered by at least one active hospital service."""
    return (db.query(Specialization)
            .filter(Specialization.id.in_(db.query(Offering.specialization_id).join(Venue)
                                          .filter(Offering.is_active.is_(True), Venue.is_active.is_(True))))
            .order_by(Specialization.name).all())


@router.get("/venues/{venue_id}", response_model=VenueDetail)
def get_venue(venue_id: str, db: Session = Depends(get_db)):
    venue = (db.query(Venue).options(selectinload(Venue.offerings).selectinload(Offering.specialization),
                                     selectinload(Venue.providers).selectinload(Provider.offerings),
                                     selectinload(Venue.room_types))
             .filter(Venue.id == venue_id).first())
    if venue is None or not venue.is_active:
        raise HTTPException(404, "This venue is not available")
    return venue_detail(venue)


@router.get("/venues/{venue_id}/slots", response_model=list[SlotOut], dependencies=[Depends(rate_limit)])
def get_slots(venue_id: str, offering_id: str, day: date = Query(alias="date"),
              provider_id: Optional[str] = None, db: Session = Depends(get_db)):
    venue = get_active_venue(db, venue_id, VenueKind.HOSPITAL, VenueKind.SHOP)
    offering = db.get(Offering, offering_id)
    if offering is None or offering.venue_id != venue.id or not offering.is_active:
        raise HTTPException(404, "This service is not offered here")
    providers = authorised_providers(db, offering, provider_id)
    if provider_id and not providers:
        raise HTTPException(404, "The selected provider does not offer this service")
    names = {p.id: p.name for p in providers}
    return [SlotOut(start_at=s.start_at, end_at=s.end_at, provider_id=s.provider_id, provider_name=names[s.provider_id])
            for s in available_slots(db, venue, offering, day, providers)]


@router.get("/venues/{venue_id}/rooms", response_model=list[QuoteOut], dependencies=[Depends(rate_limit)])
def room_availability(venue_id: str, check_in: date, check_out: date, guests: int = Query(ge=1, le=60),
                      rooms: int = Query(default=1, ge=1, le=5), db: Session = Depends(get_db)):
    """Server-calculated quote and availability for each room type that fits the party."""
    venue = get_active_venue(db, venue_id, VenueKind.HOTEL)
    hotels.validate_dates(venue, check_in, check_out, rooms)
    return [QuoteOut(**hotels.quote(db, venue.id, room_type.id, check_in, check_out, guests, rooms))
            for room_type in db.query(RoomType).filter(RoomType.venue_id == venue.id, RoomType.is_active.is_(True))
            .order_by(RoomType.nightly_rate).all()
            if guests <= room_type.max_occupancy * rooms]
