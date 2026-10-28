"""Administrator management of venues, services, providers, rooms, staff and knowledge."""
import re
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.serializers import venue_detail
from app.core.config import settings
from app.core.database import SessionLocal, get_db
from app.core.deps import require_admin
from app.core.logging_config import logger
from app.core.sessions import revoke_all
from app.models.assistant import KnowledgeDocument
from app.models.models import AuditEvent, User, UserRole
from app.models.venues import (
    Offering, Provider, ProviderOffering, RoomType, Schedule, Specialization, Venue, VenueKind, VenueStaff,
)
from app.schemas.schemas import UserOut
from app.schemas.venues import (
    OfferingIn, OfferingOut, ProviderIn, RoleUpdate, RoomTypeIn, RoomTypeOut, SpecializationOut, StaffAssignment,
    VenueDetail, VenueIn, VenueSummary,
)
from app.services import audit

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _reindex_venue(venue_id: str) -> None:
    from app.rag.ingest import sync_venue_document
    try:
        with SessionLocal() as db:
            sync_venue_document(db, venue_id)
            db.commit()
    except Exception:
        logger.exception("Knowledge re-index for venue failed; run `python -m app.rag.ingest` to retry")


def _slugify(name: str, city: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", f"{name} {city}".lower()).strip("-")[:170]


def _commit(db: Session, message: str = "That name is already in use") -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, message)


def _venue(db: Session, venue_id: str) -> Venue:
    venue = (db.query(Venue).options(selectinload(Venue.offerings), selectinload(Venue.providers)
                                     .selectinload(Provider.offerings), selectinload(Venue.room_types))
             .filter(Venue.id == venue_id).first())
    if venue is None:
        raise HTTPException(404, "Venue not found")
    return venue


# ------------------------------ Venues ------------------------------

@router.get("/venues", response_model=list[VenueSummary])
def list_all_venues(kind: Optional[VenueKind] = None, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    query = db.query(Venue)
    if kind:
        query = query.filter(Venue.kind == kind)
    return query.order_by(Venue.kind, Venue.name).all()


@router.get("/venues/{venue_id}", response_model=VenueDetail)
def admin_venue(venue_id: str, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    venue = _venue(db, venue_id)
    return venue_detail(venue, include_inactive=True)


@router.post("/venues", response_model=VenueSummary, status_code=201)
def create_venue(payload: VenueIn, request: Request, background: BackgroundTasks, db: Session = Depends(get_db),
                 admin: User = Depends(require_admin)):
    venue = Venue(**payload.model_dump(), slug=_slugify(payload.name, payload.city))
    db.add(venue)
    _commit(db, "A venue with this name already exists in that city")
    audit.record(db, "admin.venue_created", actor_id=admin.id, entity_type="venue", entity_id=venue.id,
                 request=request)
    db.commit()
    background.add_task(_reindex_venue, venue.id)
    return venue


@router.put("/venues/{venue_id}", response_model=VenueSummary)
def update_venue(venue_id: str, payload: VenueIn, request: Request, background: BackgroundTasks,
                 db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    venue = _venue(db, venue_id)
    if payload.kind != venue.kind:
        raise HTTPException(422, "A venue's type cannot be changed")
    for key, value in payload.model_dump().items():
        setattr(venue, key, value)
    audit.record(db, "admin.venue_updated", actor_id=admin.id, entity_type="venue", entity_id=venue.id,
                 request=request)
    _commit(db)
    background.add_task(_reindex_venue, venue.id)
    return venue


# ------------------------------ Offerings ------------------------------

@router.get("/specializations", response_model=list[SpecializationOut])
def all_specializations(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return db.query(Specialization).order_by(Specialization.name).all()


def _check_specialization(db: Session, venue: Venue, specialization_id: Optional[str]) -> None:
    if specialization_id and (venue.kind != VenueKind.HOSPITAL or db.get(Specialization, specialization_id) is None):
        raise HTTPException(422, "Specializations apply to hospital services only")


@router.post("/venues/{venue_id}/offerings", response_model=OfferingOut, status_code=201)
def create_offering(venue_id: str, payload: OfferingIn, background: BackgroundTasks, db: Session = Depends(get_db),
                    admin: User = Depends(require_admin)):
    venue = _venue(db, venue_id)
    if venue.kind == VenueKind.HOTEL:
        raise HTTPException(422, "Hotels use room types, not appointment services")
    _check_specialization(db, venue, payload.specialization_id)
    offering = Offering(venue_id=venue.id, **payload.model_dump())
    db.add(offering)
    _commit(db, "This venue already has a service with that name")
    audit.record(db, "admin.offering_saved", actor_id=admin.id, entity_type="offering", entity_id=offering.id)
    db.commit()
    background.add_task(_reindex_venue, venue.id)
    return offering


@router.put("/offerings/{offering_id}", response_model=OfferingOut)
def update_offering(offering_id: str, payload: OfferingIn, background: BackgroundTasks,
                    db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    offering = db.get(Offering, offering_id)
    if offering is None:
        raise HTTPException(404, "Service not found")
    _check_specialization(db, offering.venue, payload.specialization_id)
    for key, value in payload.model_dump().items():
        setattr(offering, key, value)
    audit.record(db, "admin.offering_saved", actor_id=admin.id, entity_type="offering", entity_id=offering.id)
    _commit(db, "This venue already has a service with that name")
    background.add_task(_reindex_venue, offering.venue_id)
    return offering


# ------------------------------ Providers ------------------------------

def _apply_provider(db: Session, venue: Venue, provider: Provider, payload: ProviderIn) -> None:
    _check_specialization(db, venue, payload.specialization_id)
    offering_ids = set(payload.offering_ids)
    valid = {o.id for o in db.query(Offering).filter(Offering.venue_id == venue.id, Offering.id.in_(offering_ids))}
    if valid != offering_ids:
        raise HTTPException(422, "Providers can only be assigned services of the same venue")
    for window in payload.schedules:
        if window.end_time <= window.start_time:
            raise HTTPException(422, "Each working window must end after it starts")
    for key in ("name", "title", "bio", "specialization_id", "token_prefix", "is_active"):
        setattr(provider, key, getattr(payload, key))
    db.flush()
    db.query(ProviderOffering).filter(ProviderOffering.provider_id == provider.id).delete()
    db.add_all(ProviderOffering(provider_id=provider.id, offering_id=oid) for oid in sorted(offering_ids))
    provider.schedules.clear()
    db.flush()
    provider.schedules.extend(Schedule(weekday=w.weekday, start_time=w.start_time, end_time=w.end_time)
                              for w in payload.schedules)


def _provider_out(provider: Provider) -> dict:
    return {"id": provider.id, "name": provider.name, "title": provider.title, "bio": provider.bio,
            "specialization_id": provider.specialization_id, "token_prefix": provider.token_prefix,
            "is_active": provider.is_active, "offering_ids": [o.id for o in provider.offerings],
            "schedules": [{"weekday": s.weekday, "start_time": s.start_time, "end_time": s.end_time}
                          for s in provider.schedules]}


@router.get("/venues/{venue_id}/providers")
def list_providers(venue_id: str, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return [_provider_out(p) for p in _venue(db, venue_id).providers]


@router.post("/venues/{venue_id}/providers", status_code=201)
def create_provider(venue_id: str, payload: ProviderIn, background: BackgroundTasks, db: Session = Depends(get_db),
                    admin: User = Depends(require_admin)):
    venue = _venue(db, venue_id)
    if venue.kind == VenueKind.HOTEL:
        raise HTTPException(422, "Hotels do not have appointment providers")
    provider = Provider(venue_id=venue.id, name=payload.name, token_prefix=payload.token_prefix)
    db.add(provider)
    try:
        _apply_provider(db, venue, provider, payload)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Token prefix already used at this venue")
    audit.record(db, "admin.provider_saved", actor_id=admin.id, entity_type="provider", entity_id=provider.id)
    _commit(db, "Token prefix already used at this venue")
    db.refresh(provider)
    background.add_task(_reindex_venue, venue.id)
    return _provider_out(provider)


@router.put("/providers/{provider_id}")
def update_provider(provider_id: str, payload: ProviderIn, background: BackgroundTasks,
                    db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    provider = db.get(Provider, provider_id)
    if provider is None:
        raise HTTPException(404, "Provider not found")
    try:
        _apply_provider(db, provider.venue, provider, payload)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Token prefix already used at this venue")
    audit.record(db, "admin.provider_saved", actor_id=admin.id, entity_type="provider", entity_id=provider.id)
    _commit(db, "Token prefix already used at this venue")
    db.refresh(provider)
    background.add_task(_reindex_venue, provider.venue_id)
    return _provider_out(provider)


# ------------------------------ Room types ------------------------------

@router.post("/venues/{venue_id}/room-types", response_model=RoomTypeOut, status_code=201)
def create_room_type(venue_id: str, payload: RoomTypeIn, background: BackgroundTasks, db: Session = Depends(get_db),
                     admin: User = Depends(require_admin)):
    venue = _venue(db, venue_id)
    if venue.kind != VenueKind.HOTEL:
        raise HTTPException(422, "Room types apply to hotels only")
    room_type = RoomType(venue_id=venue.id, **payload.model_dump())
    db.add(room_type)
    _commit(db, "This hotel already has a room type with that name")
    audit.record(db, "admin.room_type_saved", actor_id=admin.id, entity_type="room_type", entity_id=room_type.id)
    db.commit()
    background.add_task(_reindex_venue, venue.id)
    return room_type


@router.put("/room-types/{room_type_id}", response_model=RoomTypeOut)
def update_room_type(room_type_id: str, payload: RoomTypeIn, background: BackgroundTasks,
                     db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    room_type = db.query(RoomType).filter(RoomType.id == room_type_id).with_for_update().first()
    if room_type is None:
        raise HTTPException(404, "Room type not found")
    for key, value in payload.model_dump().items():
        setattr(room_type, key, value)
    audit.record(db, "admin.room_type_saved", actor_id=admin.id, entity_type="room_type", entity_id=room_type.id)
    _commit(db, "This hotel already has a room type with that name")
    background.add_task(_reindex_venue, room_type.venue_id)
    return room_type


# ------------------------------ Staff & users ------------------------------

@router.get("/venues/{venue_id}/staff", response_model=list[UserOut])
def venue_staff(venue_id: str, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return (db.query(User).join(VenueStaff, VenueStaff.user_id == User.id)
            .filter(VenueStaff.venue_id == venue_id).order_by(User.full_name).all())


@router.post("/venues/{venue_id}/staff", status_code=201)
def assign_staff(venue_id: str, payload: StaffAssignment, request: Request, db: Session = Depends(get_db),
                 admin: User = Depends(require_admin)):
    _venue(db, venue_id)
    user = db.get(User, payload.user_id)
    if user is None or user.role not in (UserRole.STAFF, UserRole.ADMIN):
        raise HTTPException(422, "Give the account the STAFF role before assigning it to a venue")
    if not db.get(VenueStaff, (venue_id, user.id)):
        db.add(VenueStaff(venue_id=venue_id, user_id=user.id))
        audit.record(db, "admin.staff_assigned", actor_id=admin.id, entity_type="venue", entity_id=venue_id,
                     request=request, user_id=user.id)
        db.commit()
    return {"ok": True}


@router.delete("/venues/{venue_id}/staff/{user_id}", status_code=204)
def unassign_staff(venue_id: str, user_id: str, request: Request, db: Session = Depends(get_db),
                   admin: User = Depends(require_admin)):
    link = db.get(VenueStaff, (venue_id, user_id))
    if link is not None:
        db.delete(link)
        audit.record(db, "admin.staff_unassigned", actor_id=admin.id, entity_type="venue", entity_id=venue_id,
                     request=request, user_id=user_id)
        db.commit()


@router.get("/users", response_model=list[UserOut])
def search_users(q: Optional[str] = Query(default=None, max_length=80), role: Optional[UserRole] = None,
                 limit: int = Query(50, ge=1, le=100), db: Session = Depends(get_db), _: User = Depends(require_admin)):
    query = db.query(User)
    if q:
        pattern = f"%{q.strip().lower().replace('%', '').replace('_', '')}%"
        query = query.filter(or_(User.email.ilike(pattern), User.full_name.ilike(pattern)))
    if role:
        query = query.filter(User.role == role)
    return query.order_by(User.created_at.desc()).limit(limit).all()


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: str, payload: RoleUpdate, request: Request, db: Session = Depends(get_db),
                admin: User = Depends(require_admin)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    if user.id == admin.id and (payload.role != UserRole.ADMIN.value or payload.is_active is False):
        raise HTTPException(422, "You cannot remove your own administrator access")
    previous = user.role
    user.role = UserRole(payload.role)
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if user.role == UserRole.CUSTOMER:
        db.query(VenueStaff).filter(VenueStaff.user_id == user.id).delete()
    if previous != user.role or payload.is_active is False:
        revoke_all(db, user.id)  # privilege changes take effect on next sign-in everywhere
    audit.record(db, "admin.user_updated", actor_id=admin.id, entity_type="user", entity_id=user.id,
                 request=request, from_role=previous.value, to_role=user.role.value, is_active=user.is_active)
    db.commit()
    db.refresh(user)
    return user


@router.get("/audit")
def audit_log(limit: int = Query(100, ge=1, le=500), action: Optional[str] = Query(default=None, max_length=64),
              db: Session = Depends(get_db), _: User = Depends(require_admin)):
    query = db.query(AuditEvent)
    if action:
        query = query.filter(AuditEvent.action.like(f"{action.replace('%', '')}%"))
    return [{"id": e.id, "action": e.action, "actor_id": e.actor_id, "entity_type": e.entity_type,
             "entity_id": e.entity_id, "detail": e.detail, "created_at": e.created_at}
            for e in query.order_by(AuditEvent.created_at.desc()).limit(limit).all()]


# ------------------------------ Knowledge base ------------------------------

@router.get("/knowledge")
def knowledge_status(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    from app.rag.embeddings import get_embedder
    docs = db.query(KnowledgeDocument).order_by(KnowledgeDocument.category, KnowledgeDocument.title).all()
    return {"embedding_model": get_embedder().model_id, "llm_configured": settings.llm_configured,
            "llm_provider": settings.LLM_PROVIDER or None, "llm_model": settings.LLM_MODEL or None,
            "documents": [{"id": d.id, "source": d.source, "title": d.title, "category": d.category,
                           "access_level": d.access_level, "version": d.version, "chunks": len(d.chunks),
                           "embedding_model": d.embedding_model, "indexed_at": d.indexed_at} for d in docs]}


@router.post("/knowledge/reindex")
def reindex_knowledge(request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    from app.rag.ingest import ingest_all
    try:
        result = ingest_all(db)
    except Exception:
        db.rollback()
        logger.exception("Knowledge re-index failed")
        raise HTTPException(502, "Re-indexing failed: the embedding provider could not be reached")
    audit.record(db, "admin.knowledge_reindexed", actor_id=admin.id, request=request, **result)
    db.commit()
    return result
