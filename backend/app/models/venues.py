"""Hospitals, shops and hotels.

Date/time semantics
-------------------
* Every venue has an IANA ``timezone``. Provider schedules are wall-clock
  times in that zone.
* ``Booking.start_at``/``end_at`` are stored in UTC (timestamptz);
  ``Booking.service_date`` is the venue-local calendar date of ``start_at``.
* Hotel ``check_in``/``check_out`` are venue-local calendar dates; the stay
  covers the nights ``check_in <= night < check_out``.
"""
import enum

from sqlalchemy import (
    Boolean, CheckConstraint, Column, Date, DateTime, Enum as SAEnum, ForeignKey, Index, Integer,
    Numeric, String, Text, Time, UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import ExcludeConstraint, TSTZRANGE
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.models import gen_uuid


class VenueKind(str, enum.Enum):
    HOSPITAL = "HOSPITAL"
    SHOP = "SHOP"
    HOTEL = "HOTEL"


class BookingStatus(str, enum.Enum):
    CONFIRMED = "CONFIRMED"
    CHECKED_IN = "CHECKED_IN"
    IN_SERVICE = "IN_SERVICE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    NO_SHOW = "NO_SHOW"


ACTIVE_BOOKING_STATUSES = (BookingStatus.CONFIRMED, BookingStatus.CHECKED_IN, BookingStatus.IN_SERVICE)


class ReservationStatus(str, enum.Enum):
    CONFIRMED = "CONFIRMED"
    CHECKED_IN = "CHECKED_IN"
    CHECKED_OUT = "CHECKED_OUT"
    CANCELLED = "CANCELLED"
    NO_SHOW = "NO_SHOW"


class QueueDayStatus(str, enum.Enum):
    OPEN = "OPEN"
    PAUSED = "PAUSED"


def _ts():
    return Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Venue(Base):
    __tablename__ = "venues"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    kind = Column(SAEnum(VenueKind, name="venue_kind"), nullable=False)
    name = Column(String(160), nullable=False)
    slug = Column(String(180), nullable=False, unique=True)
    city = Column(String(80), nullable=False)
    address = Column(String(255), nullable=False, default="")
    description = Column(Text, nullable=False, default="")
    phone = Column(String(32), nullable=True)
    category = Column(String(64), nullable=True)  # shop category, e.g. "Salon"
    timezone = Column(String(64), nullable=False, default="Asia/Kolkata")
    currency = Column(String(3), nullable=False, default="INR")
    is_active = Column(Boolean, nullable=False, default=True)
    # Demonstration data is labelled in the UI; it is not a real partner listing.
    is_sample = Column(Boolean, nullable=False, default=False)
    # Appointment policy (hospitals/shops)
    booking_horizon_days = Column(Integer, nullable=False, default=30)
    min_notice_minutes = Column(Integer, nullable=False, default=30)
    cancel_cutoff_minutes = Column(Integer, nullable=False, default=120)
    # Hotel policy
    tax_rate = Column(Numeric(5, 4), nullable=False, default=0)
    check_in_time = Column(Time, nullable=True)
    check_out_time = Column(Time, nullable=True)
    free_cancellation_hours = Column(Integer, nullable=False, default=24)
    created_at = _ts()
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    offerings = relationship("Offering", back_populates="venue", order_by="Offering.name")
    providers = relationship("Provider", back_populates="venue", order_by="Provider.name")
    room_types = relationship("RoomType", back_populates="venue", order_by="RoomType.nightly_rate")

    __table_args__ = (
        CheckConstraint("booking_horizon_days BETWEEN 1 AND 365", name="ck_venue_horizon"),
        CheckConstraint("min_notice_minutes BETWEEN 0 AND 10080", name="ck_venue_notice"),
        CheckConstraint("cancel_cutoff_minutes BETWEEN 0 AND 10080", name="ck_venue_cutoff"),
        CheckConstraint("tax_rate >= 0 AND tax_rate < 1", name="ck_venue_tax"),
        CheckConstraint("free_cancellation_hours BETWEEN 0 AND 720", name="ck_venue_free_cancel"),
        Index("ix_venue_kind_active_city", "kind", "is_active", "city"),
    )


class Specialization(Base):
    __tablename__ = "specializations"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    name = Column(String(80), nullable=False, unique=True)
    slug = Column(String(90), nullable=False, unique=True)
    description = Column(Text, nullable=False, default="")


class Offering(Base):
    """A bookable service: a hospital consultation or a shop service."""
    __tablename__ = "offerings"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    venue_id = Column(String(36), ForeignKey("venues.id", ondelete="CASCADE"), nullable=False)
    specialization_id = Column(String(36), ForeignKey("specializations.id"), nullable=True, index=True)
    name = Column(String(120), nullable=False)
    description = Column(Text, nullable=False, default="")
    duration_minutes = Column(Integer, nullable=False, default=15)
    price = Column(Numeric(10, 2), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = _ts()

    venue = relationship("Venue", back_populates="offerings")
    specialization = relationship("Specialization")
    providers = relationship("Provider", secondary="provider_offerings", back_populates="offerings")

    __table_args__ = (
        UniqueConstraint("venue_id", "name", name="uq_offering_venue_name"),
        CheckConstraint("duration_minutes BETWEEN 5 AND 480", name="ck_offering_duration"),
        CheckConstraint("price IS NULL OR price >= 0", name="ck_offering_price"),
        Index("ix_offering_venue_active", "venue_id", "is_active"),
    )


class Provider(Base):
    """A doctor (hospital) or staff member (shop) who serves appointments."""
    __tablename__ = "providers"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    venue_id = Column(String(36), ForeignKey("venues.id", ondelete="CASCADE"), nullable=False, index=True)
    specialization_id = Column(String(36), ForeignKey("specializations.id"), nullable=True)
    name = Column(String(120), nullable=False)
    title = Column(String(120), nullable=False, default="")
    bio = Column(Text, nullable=False, default="")
    token_prefix = Column(String(8), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = _ts()

    venue = relationship("Venue", back_populates="providers")
    specialization = relationship("Specialization")
    offerings = relationship("Offering", secondary="provider_offerings", back_populates="providers")
    schedules = relationship("Schedule", back_populates="provider", order_by="(Schedule.weekday, Schedule.start_time)",
                             cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("venue_id", "token_prefix", name="uq_provider_token_prefix"),
        CheckConstraint("token_prefix ~ '^[A-Z0-9]{1,8}$'", name="ck_provider_prefix"),
    )


class ProviderOffering(Base):
    """Which providers are authorised to deliver which offerings."""
    __tablename__ = "provider_offerings"

    provider_id = Column(String(36), ForeignKey("providers.id", ondelete="CASCADE"), primary_key=True)
    offering_id = Column(String(36), ForeignKey("offerings.id", ondelete="CASCADE"), primary_key=True)


class Schedule(Base):
    """Weekly working window in venue-local wall time (weekday: Monday=0)."""
    __tablename__ = "schedules"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    provider_id = Column(String(36), ForeignKey("providers.id", ondelete="CASCADE"), nullable=False, index=True)
    weekday = Column(Integer, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)

    provider = relationship("Provider", back_populates="schedules")

    __table_args__ = (
        CheckConstraint("weekday BETWEEN 0 AND 6", name="ck_schedule_weekday"),
        CheckConstraint("end_time > start_time", name="ck_schedule_window"),
        UniqueConstraint("provider_id", "weekday", "start_time", name="uq_schedule_window"),
    )


class VenueStaff(Base):
    """Staff accounts authorised to operate a venue's queues and reservations."""
    __tablename__ = "venue_staff"

    venue_id = Column(String(36), ForeignKey("venues.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True)
    created_at = _ts()


class QueueDay(Base):
    """One provider's queue for one venue-local service date. Holds the token
    counter; locking this row serialises token issue for that queue."""
    __tablename__ = "queue_days"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    provider_id = Column(String(36), ForeignKey("providers.id", ondelete="CASCADE"), nullable=False)
    service_date = Column(Date, nullable=False)
    next_token = Column(Integer, nullable=False, default=1)
    status = Column(SAEnum(QueueDayStatus, name="queue_day_status"), nullable=False, default=QueueDayStatus.OPEN)
    delay_minutes = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    provider = relationship("Provider")

    __table_args__ = (
        UniqueConstraint("provider_id", "service_date", name="uq_queue_day"),
        CheckConstraint("next_token >= 1", name="ck_queue_day_token"),
        CheckConstraint("delay_minutes BETWEEN 0 AND 600", name="ck_queue_day_delay"),
    )


_ACTIVE_SQL = "status IN ('CONFIRMED', 'CHECKED_IN', 'IN_SERVICE')"


class Booking(Base):
    """A hospital or shop appointment with a queue token."""
    __tablename__ = "bookings"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    reference = Column(String(16), nullable=False, unique=True)
    customer_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    venue_id = Column(String(36), ForeignKey("venues.id"), nullable=False)
    offering_id = Column(String(36), ForeignKey("offerings.id"), nullable=False)
    provider_id = Column(String(36), ForeignKey("providers.id"), nullable=False)
    queue_day_id = Column(String(36), ForeignKey("queue_days.id"), nullable=False)
    start_at = Column(DateTime(timezone=True), nullable=False)
    end_at = Column(DateTime(timezone=True), nullable=False)
    service_date = Column(Date, nullable=False)
    token_number = Column(Integer, nullable=False)
    token_label = Column(String(16), nullable=False)
    status = Column(SAEnum(BookingStatus, name="booking_status"), nullable=False, default=BookingStatus.CONFIRMED)
    notes = Column(String(500), nullable=True)
    idempotency_key = Column(String(64), nullable=True)
    checked_in_at = Column(DateTime(timezone=True), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = _ts()
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    venue = relationship("Venue")
    offering = relationship("Offering")
    provider = relationship("Provider")
    queue_day = relationship("QueueDay")
    customer = relationship("User")

    __table_args__ = (
        CheckConstraint("end_at > start_at", name="ck_booking_window"),
        UniqueConstraint("customer_id", "idempotency_key", name="uq_booking_idempotency"),
        UniqueConstraint("queue_day_id", "token_number", name="uq_booking_token"),
        # Database-level guarantee: a provider can never hold two active
        # bookings whose time ranges overlap, whatever the application does.
        ExcludeConstraint(
            ("provider_id", "="),
            (func.tstzrange(text("start_at"), text("end_at"), text("'[)'")), "&&"),
            name="ex_booking_provider_overlap",
            using="gist",
            where=text(_ACTIVE_SQL),
        ),
        Index("ix_booking_customer_start", "customer_id", "start_at"),
        Index("ix_booking_queue_day_status", "queue_day_id", "status"),
        Index("ix_booking_venue_date", "venue_id", "service_date"),
    )


class RoomType(Base):
    __tablename__ = "room_types"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    venue_id = Column(String(36), ForeignKey("venues.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    description = Column(Text, nullable=False, default="")
    amenities = Column(String(500), nullable=False, default="")
    max_occupancy = Column(Integer, nullable=False)
    nightly_rate = Column(Numeric(10, 2), nullable=False)
    total_rooms = Column(Integer, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = _ts()

    venue = relationship("Venue", back_populates="room_types")

    __table_args__ = (
        UniqueConstraint("venue_id", "name", name="uq_room_type_name"),
        CheckConstraint("max_occupancy BETWEEN 1 AND 12", name="ck_room_occupancy"),
        CheckConstraint("nightly_rate >= 0", name="ck_room_rate"),
        CheckConstraint("total_rooms BETWEEN 0 AND 10000", name="ck_room_total"),
    )


class RoomInventory(Base):
    """Rooms of a type already sold for one night. Rows are created lazily and
    incremented with a guarded atomic UPDATE, so inventory cannot go negative
    or exceed the room type's capacity."""
    __tablename__ = "room_inventory"

    room_type_id = Column(String(36), ForeignKey("room_types.id", ondelete="CASCADE"), primary_key=True)
    night = Column(Date, primary_key=True)
    booked = Column(Integer, nullable=False, default=0)

    __table_args__ = (CheckConstraint("booked >= 0", name="ck_inventory_booked"),)


class Reservation(Base):
    __tablename__ = "reservations"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    reference = Column(String(16), nullable=False, unique=True)
    customer_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    venue_id = Column(String(36), ForeignKey("venues.id"), nullable=False)
    room_type_id = Column(String(36), ForeignKey("room_types.id"), nullable=False)
    check_in = Column(Date, nullable=False)
    check_out = Column(Date, nullable=False)
    guests = Column(Integer, nullable=False)
    rooms = Column(Integer, nullable=False, default=1)
    nights = Column(Integer, nullable=False)
    nightly_rate = Column(Numeric(10, 2), nullable=False)
    subtotal = Column(Numeric(12, 2), nullable=False)
    taxes = Column(Numeric(12, 2), nullable=False)
    total = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), nullable=False)
    status = Column(SAEnum(ReservationStatus, name="reservation_status"), nullable=False,
                    default=ReservationStatus.CONFIRMED)
    cancellation_fee = Column(Numeric(12, 2), nullable=False, default=0)
    special_requests = Column(String(500), nullable=True)
    idempotency_key = Column(String(64), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = _ts()
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    venue = relationship("Venue")
    room_type = relationship("RoomType")
    customer = relationship("User")

    __table_args__ = (
        CheckConstraint("check_out > check_in", name="ck_reservation_dates"),
        CheckConstraint("guests >= 1", name="ck_reservation_guests"),
        CheckConstraint("rooms BETWEEN 1 AND 5", name="ck_reservation_rooms"),
        CheckConstraint("nights >= 1", name="ck_reservation_nights"),
        UniqueConstraint("customer_id", "idempotency_key", name="uq_reservation_idempotency"),
        Index("ix_reservation_customer_checkin", "customer_id", "check_in"),
        Index("ix_reservation_venue_checkin", "venue_id", "check_in"),
    )


__all__ = [
    "VenueKind", "BookingStatus", "ReservationStatus", "QueueDayStatus", "ACTIVE_BOOKING_STATUSES",
    "Venue", "Specialization", "Offering", "Provider", "ProviderOffering", "Schedule", "VenueStaff",
    "QueueDay", "Booking", "RoomType", "RoomInventory", "Reservation", "TSTZRANGE",
]
