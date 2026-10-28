from datetime import timedelta

from sqlalchemy.orm import Session

from app.models.venues import Booking, BookingStatus, Reservation, Venue
from app.schemas.venues import BookingOut, LiveQueue, ProviderOut, ReservationOut, VenueDetail
from app.services.booking import hotels, queue_ops
from app.services.booking.common import as_utc, local_today, utcnow


def booking_out(db: Session, booking: Booking, live: bool = False) -> BookingOut:
    venue = booking.venue
    can_cancel = (booking.status == BookingStatus.CONFIRMED
                  and utcnow() <= as_utc(booking.start_at) - timedelta(minutes=venue.cancel_cutoff_minutes))
    live_data = None
    # Live queue position/estimates are only meaningful on the visit day itself.
    if live and booking.status in (BookingStatus.CONFIRMED, BookingStatus.CHECKED_IN, BookingStatus.IN_SERVICE) \
            and booking.service_date == local_today(venue):
        live_data = LiveQueue(**queue_ops.booking_live(db, booking))
    spec = booking.offering.specialization
    return BookingOut(
        id=booking.id, reference=booking.reference, status=booking.status, venue_id=venue.id, venue_name=venue.name,
        venue_kind=venue.kind, venue_timezone=venue.timezone, offering_id=booking.offering_id,
        offering_name=booking.offering.name, specialization=spec.name if spec else None,
        provider_id=booking.provider_id, provider_name=booking.provider.name, start_at=as_utc(booking.start_at),
        end_at=as_utc(booking.end_at), service_date=booking.service_date, token_label=booking.token_label,
        notes=booking.notes, can_cancel=can_cancel, cancel_cutoff_minutes=venue.cancel_cutoff_minutes,
        created_at=booking.created_at, live=live_data)


def reservation_out(reservation: Reservation) -> ReservationOut:
    venue = reservation.venue
    return ReservationOut(
        id=reservation.id, reference=reservation.reference, status=reservation.status, venue_id=venue.id,
        venue_name=venue.name, venue_timezone=venue.timezone, room_type_id=reservation.room_type_id,
        room_type_name=reservation.room_type.name, check_in=reservation.check_in, check_out=reservation.check_out,
        check_in_time=venue.check_in_time, check_out_time=venue.check_out_time, guests=reservation.guests,
        rooms=reservation.rooms, nights=reservation.nights, nightly_rate=reservation.nightly_rate,
        subtotal=reservation.subtotal, taxes=reservation.taxes, total=reservation.total,
        currency=reservation.currency, cancellation_fee=reservation.cancellation_fee,
        special_requests=reservation.special_requests,
        free_cancellation_until=hotels.free_cancellation_until(venue, reservation.check_in),
        created_at=reservation.created_at)


def venue_detail(venue: Venue, include_inactive: bool = False) -> VenueDetail:
    offerings = [o for o in venue.offerings if include_inactive or o.is_active]
    providers = [p for p in venue.providers if include_inactive or p.is_active]
    specs = {o.specialization.id: o.specialization for o in offerings if o.specialization is not None}
    return VenueDetail.model_validate({
        **{c.name: getattr(venue, c.name) for c in Venue.__table__.columns},
        "specializations": sorted(specs.values(), key=lambda s: s.name),
        "offerings": offerings,
        "providers": [ProviderOut.model_validate({**{c: getattr(p, c) for c in (
            "id", "name", "title", "bio", "specialization_id", "is_active")},
            "offering_ids": [o.id for o in p.offerings if include_inactive or o.is_active]}) for p in providers],
        "room_types": [r for r in venue.room_types if include_inactive or r.is_active],
    })
