"""Allowlisted, typed tools Wayzen may call.

Rules enforced here, not in the prompt:
* Every argument is validated by a Pydantic model; unknown fields are rejected.
* Tools run as the signed-in user through the same services and checks as the
  web UI; the model never decides permissions.
* Read tools return only public catalogue data or the user's own records.
* "prepare_*" tools never change bookings. They re-check availability and
  store a PendingAction; only the user's Confirm button (a separate,
  CSRF-protected endpoint) can execute it, exactly once.
"""
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Callable, Literal, Optional

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.api.serializers import booking_out, reservation_out
from app.models.assistant import PendingAction
from app.models.models import User
from app.models.venues import (
    ACTIVE_BOOKING_STATUSES, Booking, Offering, Provider, Reservation, ReservationStatus, Venue, VenueKind,
)
from app.services import audit
from app.services.booking import appointments, hotels
from app.services.booking.common import as_utc, get_active_venue, utcnow, venue_tz
from app.services.booking.slots import authorised_providers, available_slots, provider_slots

ACTION_TTL = timedelta(minutes=15)
MAX_ACTIONS_PER_TURN = 2


class Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SearchVenues(Args):
    kind: Optional[Literal["HOSPITAL", "SHOP", "HOTEL"]] = None
    query: Optional[str] = Field(default=None, max_length=80)
    city: Optional[str] = Field(default=None, max_length=80)
    specialization: Optional[str] = Field(default=None, max_length=80)


class VenueRef(Args):
    venue_id: str = Field(max_length=36)


class FindSlots(Args):
    venue_id: str = Field(max_length=36)
    offering_id: str = Field(max_length=36)
    date: date
    provider_id: Optional[str] = Field(default=None, max_length=36)


class HotelQuery(Args):
    venue_id: str = Field(max_length=36)
    check_in: date
    check_out: date
    guests: int = Field(ge=1, le=60)
    rooms: int = Field(default=1, ge=1, le=5)


class NoArgs(Args):
    pass


class PrepareAppointment(Args):
    venue_id: str = Field(max_length=36)
    offering_id: str = Field(max_length=36)
    provider_id: str = Field(max_length=36)
    start_at: datetime
    notes: Optional[str] = Field(default=None, max_length=300)

    @field_validator("start_at")
    @classmethod
    def aware(cls, value):
        if value.tzinfo is None:
            raise ValueError("start_at must be an ISO timestamp with timezone, copied from find_appointment_slots")
        return value


class PrepareReservation(HotelQuery):
    room_type_id: str = Field(max_length=36)
    special_requests: Optional[str] = Field(default=None, max_length=300)


class PrepareCancellation(Args):
    reference: str = Field(pattern=r"^QF-[HSR]-[A-Z0-9]{7}$")


@dataclass
class ToolContext:
    db: Session
    user: User
    session_id: str
    actions: list[PendingAction] = field(default_factory=list)


def _local(venue: Venue, when: datetime) -> str:
    return as_utc(when).astimezone(venue_tz(venue)).strftime("%A %d %B %Y, %I:%M %p")


def search_venues(ctx: ToolContext, a: SearchVenues) -> Any:
    from app.api.venues import list_venues
    page = list_venues(kind=VenueKind(a.kind) if a.kind else None, q=a.query, city=a.city, specialization=None,
                       limit=8, offset=0, db=ctx.db)
    items = page.items
    if a.specialization:
        needle = a.specialization.lower()
        items = [v for v in items if any(o.specialization and needle in o.specialization.name.lower()
                                         for o in ctx.db.get(Venue, v.id).offerings if o.is_active)]
    return [{"venue_id": v.id, "name": v.name, "kind": v.kind.value, "city": v.city, "category": v.category,
             "sample_listing": v.is_sample} for v in items]


def get_venue_details(ctx: ToolContext, a: VenueRef) -> Any:
    venue = get_active_venue(ctx.db, a.venue_id)
    data: dict[str, Any] = {"venue_id": venue.id, "name": venue.name, "kind": venue.kind.value, "city": venue.city,
                            "address": venue.address, "timezone": venue.timezone, "sample_listing": venue.is_sample}
    if venue.kind == VenueKind.HOTEL:
        data["room_types"] = [{"room_type_id": r.id, "name": r.name, "max_occupancy": r.max_occupancy,
                               "nightly_rate": str(r.nightly_rate), "currency": venue.currency}
                              for r in venue.room_types if r.is_active]
        data["policy"] = {"free_cancellation_hours_before_check_in": venue.free_cancellation_hours,
                          "tax_rate": str(venue.tax_rate)}
    else:
        data["services"] = [{"offering_id": o.id, "name": o.name, "duration_minutes": o.duration_minutes,
                             "price": str(o.price) if o.price is not None else None,
                             "specialization": o.specialization.name if o.specialization else None}
                            for o in venue.offerings if o.is_active]
        data["providers"] = [{"provider_id": p.id, "name": p.name, "title": p.title,
                              "offering_ids": [o.id for o in p.offerings if o.is_active]}
                             for p in venue.providers if p.is_active]
        data["policy"] = {"cancel_cutoff_minutes": venue.cancel_cutoff_minutes,
                          "booking_horizon_days": venue.booking_horizon_days}
    return data


def find_appointment_slots(ctx: ToolContext, a: FindSlots) -> Any:
    venue = get_active_venue(ctx.db, a.venue_id, VenueKind.HOSPITAL, VenueKind.SHOP)
    offering = ctx.db.get(Offering, a.offering_id)
    if offering is None or offering.venue_id != venue.id or not offering.is_active:
        raise HTTPException(404, "That service is not offered at this venue")
    providers = authorised_providers(ctx.db, offering, a.provider_id)
    names = {p.id: p.name for p in providers}
    slots = available_slots(ctx.db, venue, offering, a.date, providers)
    return {"date": a.date.isoformat(), "timezone": venue.timezone, "slot_count": len(slots),
            "slots": [{"start_at": s.start_at.isoformat(), "local_time": _local(venue, s.start_at),
                       "provider_id": s.provider_id, "provider_name": names[s.provider_id]} for s in slots[:12]]}


def check_hotel_availability(ctx: ToolContext, a: HotelQuery) -> Any:
    from app.api.venues import room_availability
    quotes = room_availability(a.venue_id, a.check_in, a.check_out, a.guests, a.rooms, ctx.db)
    return [{"room_type_id": q.room_type_id, "name": q.room_type_name, "available": q.available,
             "rooms_left": q.rooms_left, "nights": q.nights, "total": str(q.total), "taxes": str(q.taxes),
             "currency": q.currency} for q in quotes]


def list_my_bookings(ctx: ToolContext, a: NoArgs) -> Any:
    now = utcnow()
    bookings = (ctx.db.query(Booking).filter(Booking.customer_id == ctx.user.id,
                                             Booking.status.in_(ACTIVE_BOOKING_STATUSES), Booking.end_at >= now)
                .order_by(Booking.start_at).limit(10).all())
    reservations = (ctx.db.query(Reservation).filter(
        Reservation.customer_id == ctx.user.id,
        Reservation.status.in_([ReservationStatus.CONFIRMED, ReservationStatus.CHECKED_IN]),
        Reservation.check_out >= now.date()).order_by(Reservation.check_in).limit(10).all())
    result = []
    for b in bookings:
        out = booking_out(ctx.db, b, live=True)
        result.append({"type": "appointment", "reference": out.reference, "venue": out.venue_name,
                       "service": out.offering_name, "provider": out.provider_name, "token": out.token_label,
                       "status": out.status.value, "local_time": _local(b.venue, b.start_at),
                       "queue_position": out.live.position if out.live else None,
                       "estimated_wait_minutes": out.live.eta_minutes if out.live else None})
    for r in reservations:
        out = reservation_out(r)
        result.append({"type": "hotel", "reference": out.reference, "hotel": out.venue_name,
                       "room_type": out.room_type_name, "check_in": str(out.check_in),
                       "check_out": str(out.check_out), "status": out.status.value,
                       "total": f"{out.currency} {out.total}"})
    return result


def _create_action(ctx: ToolContext, action_type: str, arguments: dict, summary: dict) -> dict:
    if len(ctx.actions) >= MAX_ACTIONS_PER_TURN:
        raise HTTPException(429, "Too many actions prepared in one message")
    action = PendingAction(session_id=ctx.session_id, user_id=ctx.user.id, action_type=action_type,
                           arguments=arguments, summary=summary, status="pending",
                           expires_at=utcnow() + ACTION_TTL)
    ctx.db.add(action)
    ctx.db.flush()
    audit.record(ctx.db, "wayzen.action_prepared", actor_id=ctx.user.id, entity_type="pending_action",
                 entity_id=action.id, action_type=action_type)
    ctx.actions.append(action)
    return {"action_id": action.id, "summary": summary, "status": "awaiting_user_confirmation",
            "instruction": "Show this summary and ask the user to press Confirm on the card. You cannot confirm it."}


def prepare_appointment_booking(ctx: ToolContext, a: PrepareAppointment) -> Any:
    venue = get_active_venue(ctx.db, a.venue_id, VenueKind.HOSPITAL, VenueKind.SHOP)
    offering = ctx.db.get(Offering, a.offering_id)
    if offering is None or offering.venue_id != venue.id or not offering.is_active:
        raise HTTPException(404, "That service is not offered at this venue")
    providers = authorised_providers(ctx.db, offering, a.provider_id)
    if not providers:
        raise HTTPException(404, "That provider does not offer this service")
    start = as_utc(a.start_at)
    day = start.astimezone(venue_tz(venue)).date()
    if not any(s.start_at == start for s in provider_slots(ctx.db, venue, offering, providers[0], day)):
        raise HTTPException(409, "That time is not available. Use find_appointment_slots to get current times.")
    summary = {"title": "Confirm appointment", "venue": venue.name, "service": offering.name,
               "provider": providers[0].name, "when": _local(venue, start),
               "duration_minutes": offering.duration_minutes,
               "price": f"{venue.currency} {offering.price}" if offering.price is not None else None,
               "sample_listing": venue.is_sample}
    return _create_action(ctx, "book_appointment", {"venue_id": venue.id, "offering_id": offering.id,
                                                    "provider_id": providers[0].id, "start_at": start.isoformat(),
                                                    "notes": a.notes}, summary)


def prepare_hotel_reservation(ctx: ToolContext, a: PrepareReservation) -> Any:
    quote = hotels.quote(ctx.db, a.venue_id, a.room_type_id, a.check_in, a.check_out, a.guests, a.rooms)
    if not quote["available"]:
        raise HTTPException(409, "That room type is not available for those dates")
    venue = ctx.db.get(Venue, a.venue_id)
    summary = {"title": "Confirm hotel reservation", "venue": venue.name, "room_type": quote["room_type_name"],
               "check_in": a.check_in.isoformat(), "check_out": a.check_out.isoformat(), "guests": a.guests,
               "rooms": a.rooms, "nights": quote["nights"],
               "price": f"{quote['currency']} {quote['total']} (incl. {quote['currency']} {quote['taxes']} taxes)",
               "free_cancellation_until": _local(venue, quote["free_cancellation_until"]),
               "sample_listing": venue.is_sample}
    return _create_action(ctx, "reserve_hotel", {**a.model_dump(mode="json")}, summary)


def prepare_cancellation(ctx: ToolContext, a: PrepareCancellation) -> Any:
    if a.reference.startswith("QF-R-"):
        reservation = ctx.db.query(Reservation).filter(Reservation.reference == a.reference).first()
        if reservation is None or reservation.customer_id != ctx.user.id:
            raise HTTPException(404, "No reservation with that reference in your account")
        if reservation.status != ReservationStatus.CONFIRMED:
            raise HTTPException(409, "That reservation cannot be cancelled")
        terms = hotels.cancellation_terms(reservation)
        summary = {"title": "Cancel hotel reservation", "reference": a.reference, "venue": reservation.venue.name,
                   "stay": f"{reservation.check_in} to {reservation.check_out}",
                   "charge": f"{terms['currency']} {terms['fee']}" if terms["late"] else "No charge"}
        return _create_action(ctx, "cancel_reservation", {"reference": a.reference}, summary)
    booking = ctx.db.query(Booking).filter(Booking.reference == a.reference).first()
    if booking is None or booking.customer_id != ctx.user.id:
        raise HTTPException(404, "No booking with that reference in your account")
    out = booking_out(ctx.db, booking)
    if not out.can_cancel:
        raise HTTPException(409, "This booking can no longer be cancelled online")
    summary = {"title": "Cancel appointment", "reference": a.reference, "venue": out.venue_name,
               "service": out.offering_name, "when": _local(booking.venue, booking.start_at)}
    return _create_action(ctx, "cancel_booking", {"reference": a.reference}, summary)


@dataclass
class Tool:
    name: str
    description: str
    args: type[Args]
    run: Callable[[ToolContext, Any], Any]

    def spec(self) -> dict:
        schema = self.args.model_json_schema()
        schema.pop("title", None)
        return {"name": self.name, "description": self.description, "parameters": schema}


TOOLS = {t.name: t for t in [
    Tool("search_venues", "Search active hospitals, shops or hotels by kind, name/keyword, city or specialization.",
         SearchVenues, search_venues),
    Tool("get_venue_details", "Services, doctors/staff, room types and policies of one venue.", VenueRef,
         get_venue_details),
    Tool("find_appointment_slots", "Currently free appointment times for a hospital/shop service on a date "
         "(YYYY-MM-DD, venue-local).", FindSlots, find_appointment_slots),
    Tool("check_hotel_availability", "Room availability and server-calculated prices for a stay.", HotelQuery,
         check_hotel_availability),
    Tool("list_my_bookings", "The signed-in user's upcoming appointments and hotel reservations.", NoArgs,
         list_my_bookings),
    Tool("prepare_appointment_booking", "Prepare (NOT book) an appointment for the user to confirm. start_at must "
         "be copied exactly from find_appointment_slots.", PrepareAppointment, prepare_appointment_booking),
    Tool("prepare_hotel_reservation", "Prepare (NOT book) a hotel reservation for the user to confirm.",
         PrepareReservation, prepare_hotel_reservation),
    Tool("prepare_cancellation", "Prepare (NOT perform) cancellation of one of the user's bookings by reference.",
         PrepareCancellation, prepare_cancellation),
]}


def run_tool(ctx: ToolContext, name: str, arguments: dict) -> dict:
    tool = TOOLS.get(name)
    if tool is None:
        return {"error": f"Unknown tool {name!r}. Only the listed tools are available."}
    try:
        parsed = tool.args.model_validate(arguments)
    except ValidationError as error:
        return {"error": "Invalid arguments", "details": [e["msg"] for e in error.errors()][:5]}
    savepoint = ctx.db.begin_nested()
    try:
        result = tool.run(ctx, parsed)
        savepoint.commit()
        return {"result": result}
    except HTTPException as error:
        savepoint.rollback()
        return {"error": str(error.detail)}


def execute_action(db: Session, user: User, action_id: str) -> dict:
    """Run a prepared action after the user pressed Confirm.

    The action is claimed with an atomic pending->executed update before any
    work happens, so a double click or a replayed request cannot run it twice;
    the action id is also the booking idempotency key."""
    action = db.query(PendingAction).filter(PendingAction.id == action_id).first()
    if action is None or action.user_id != user.id:
        raise HTTPException(404, "Action not found")
    if action.status == "pending" and as_utc(action.expires_at) <= utcnow():
        action.status = "expired"
        db.commit()
    claimed = db.execute(update(PendingAction).where(PendingAction.id == action_id,
                                                     PendingAction.status == "pending")
                         .values(status="executed", executed_at=utcnow()).returning(PendingAction.id)).first()
    db.commit()
    if claimed is None:
        db.refresh(action)
        if action.status == "executed":
            return {"status": "executed", "result": action.result, "repeated": True}
        raise HTTPException(409, "This summary expired. Ask Wayzen to prepare it again."
                            if action.status == "expired" else f"This action is {action.status}")
    args, key = action.arguments, f"wayzen-{action.id}"
    try:
        if action.action_type == "book_appointment":
            booking, _ = appointments.create_booking(
                db, user, venue_id=args["venue_id"], offering_id=args["offering_id"], provider_id=args["provider_id"],
                start_at=datetime.fromisoformat(args["start_at"]), notes=args.get("notes"), idempotency_key=key,
                source="wayzen")
            result = {"kind": "booking", "reference": booking.reference, "token": booking.token_label}
        elif action.action_type == "reserve_hotel":
            reservation, _ = hotels.create_reservation(
                db, user, venue_id=args["venue_id"], room_type_id=args["room_type_id"],
                check_in=date.fromisoformat(args["check_in"]), check_out=date.fromisoformat(args["check_out"]),
                guests=args["guests"], rooms=args.get("rooms", 1), special_requests=args.get("special_requests"),
                idempotency_key=key, source="wayzen")
            result = {"kind": "reservation", "reference": reservation.reference, "total": str(reservation.total)}
        elif action.action_type == "cancel_booking":
            booking = appointments.cancel_booking(db, user, args["reference"], source="wayzen")
            result = {"kind": "booking", "reference": booking.reference, "status": booking.status.value}
        else:
            reservation = hotels.cancel_reservation(db, user, args["reference"], source="wayzen")
            result = {"kind": "reservation", "reference": reservation.reference,
                      "status": reservation.status.value, "fee": str(reservation.cancellation_fee)}
    except HTTPException as error:
        db.rollback()
        db.execute(update(PendingAction).where(PendingAction.id == action_id)
                   .values(status="failed", result={"error": str(error.detail)}))
        db.commit()
        raise
    db.execute(update(PendingAction).where(PendingAction.id == action_id).values(result=result))
    audit.record(db, "wayzen.action_executed", actor_id=user.id, entity_type="pending_action", entity_id=action_id,
                 action_type=action.action_type, reference=result.get("reference"))
    db.commit()
    return {"status": "executed", "result": result, "repeated": False}


__all__ = ["TOOLS", "ToolContext", "run_tool", "execute_action", "Provider"]
