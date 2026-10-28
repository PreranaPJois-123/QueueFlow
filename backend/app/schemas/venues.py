from datetime import date, datetime, time
from decimal import Decimal
from typing import Generic, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.venues import BookingStatus, ReservationStatus, VenueKind

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ------------------------------ Public catalogue ------------------------------

class SpecializationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    slug: str
    description: str


class OfferingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    description: str
    duration_minutes: int
    price: Optional[Decimal] = None
    specialization_id: Optional[str] = None
    is_active: bool


class ProviderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    title: str
    bio: str
    specialization_id: Optional[str] = None
    is_active: bool
    offering_ids: list[str] = []


class RoomTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    description: str
    amenities: str
    max_occupancy: int
    nightly_rate: Decimal
    total_rooms: int
    is_active: bool


class VenueSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    kind: VenueKind
    name: str
    slug: str
    city: str
    address: str
    description: str
    category: Optional[str] = None
    is_sample: bool
    is_active: bool = True
    currency: str
    timezone: str


class VenueDetail(VenueSummary):
    phone: Optional[str] = None
    booking_horizon_days: int
    min_notice_minutes: int
    cancel_cutoff_minutes: int
    tax_rate: Decimal
    check_in_time: Optional[time] = None
    check_out_time: Optional[time] = None
    free_cancellation_hours: int
    specializations: list[SpecializationOut] = []
    offerings: list[OfferingOut] = []
    providers: list[ProviderOut] = []
    room_types: list[RoomTypeOut] = []


class SlotOut(BaseModel):
    start_at: datetime
    end_at: datetime
    provider_id: str
    provider_name: str


class QuoteOut(BaseModel):
    room_type_id: str
    room_type_name: str
    check_in: date
    check_out: date
    guests: int
    rooms: int
    nights: int
    nightly_rate: Decimal
    subtotal: Decimal
    tax_rate: Decimal
    taxes: Decimal
    total: Decimal
    currency: str
    rooms_left: int
    available: bool
    free_cancellation_until: datetime


# ------------------------------ Customer bookings ------------------------------

class BookingCreate(Strict):
    venue_id: str = Field(max_length=36)
    offering_id: str = Field(max_length=36)
    provider_id: Optional[str] = Field(default=None, max_length=36)
    start_at: datetime
    notes: Optional[str] = Field(default=None, max_length=500)

    @field_validator("start_at")
    @classmethod
    def aware(cls, value: datetime):
        if value.tzinfo is None:
            raise ValueError("start_at must include a timezone")
        return value

    @field_validator("notes")
    @classmethod
    def clean(cls, value):
        return value.strip() or None if value else None


class BookingReschedule(Strict):
    start_at: datetime
    provider_id: Optional[str] = Field(default=None, max_length=36)

    @field_validator("start_at")
    @classmethod
    def aware(cls, value: datetime):
        if value.tzinfo is None:
            raise ValueError("start_at must include a timezone")
        return value


class LiveQueue(BaseModel):
    queue_status: str
    current_token: Optional[str] = None
    delay_minutes: int
    position: Optional[int] = None
    eta_minutes: Optional[int] = None
    expected_start: Optional[datetime] = None


class BookingOut(BaseModel):
    id: str
    reference: str
    status: BookingStatus
    venue_id: str
    venue_name: str
    venue_kind: VenueKind
    venue_timezone: str
    offering_id: str
    offering_name: str
    specialization: Optional[str] = None
    provider_id: str
    provider_name: str
    start_at: datetime
    end_at: datetime
    service_date: date
    token_label: str
    notes: Optional[str] = None
    can_cancel: bool
    cancel_cutoff_minutes: int
    created_at: datetime
    live: Optional[LiveQueue] = None


class ReservationCreate(Strict):
    venue_id: str = Field(max_length=36)
    room_type_id: str = Field(max_length=36)
    check_in: date
    check_out: date
    guests: int = Field(ge=1, le=60)
    rooms: int = Field(default=1, ge=1, le=5)
    special_requests: Optional[str] = Field(default=None, max_length=500)


class ReservationModify(Strict):
    check_in: date
    check_out: date
    guests: int = Field(ge=1, le=60)
    room_type_id: Optional[str] = Field(default=None, max_length=36)


class ReservationOut(BaseModel):
    id: str
    reference: str
    status: ReservationStatus
    venue_id: str
    venue_name: str
    venue_timezone: str
    room_type_id: str
    room_type_name: str
    check_in: date
    check_out: date
    check_in_time: Optional[time] = None
    check_out_time: Optional[time] = None
    guests: int
    rooms: int
    nights: int
    nightly_rate: Decimal
    subtotal: Decimal
    taxes: Decimal
    total: Decimal
    currency: str
    cancellation_fee: Decimal
    special_requests: Optional[str] = None
    free_cancellation_until: datetime
    created_at: datetime


# ------------------------------ Staff / admin ------------------------------

class QueueControl(Strict):
    paused: Optional[bool] = None
    delay_minutes: Optional[int] = Field(default=None, ge=0, le=600)


class VenueIn(Strict):
    kind: VenueKind
    name: str = Field(min_length=2, max_length=160)
    city: str = Field(min_length=2, max_length=80)
    address: str = Field(default="", max_length=255)
    description: str = Field(default="", max_length=4000)
    phone: Optional[str] = Field(default=None, max_length=32)
    category: Optional[str] = Field(default=None, max_length=64)
    timezone: str = Field(default="Asia/Kolkata", max_length=64)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    is_active: bool = True
    booking_horizon_days: int = Field(default=30, ge=1, le=365)
    min_notice_minutes: int = Field(default=30, ge=0, le=10080)
    cancel_cutoff_minutes: int = Field(default=120, ge=0, le=10080)
    tax_rate: Decimal = Field(default=Decimal("0"), ge=0, lt=1)
    check_in_time: Optional[time] = None
    check_out_time: Optional[time] = None
    free_cancellation_hours: int = Field(default=24, ge=0, le=720)

    @field_validator("timezone")
    @classmethod
    def valid_tz(cls, value):
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Unknown timezone")
        return value


class OfferingIn(Strict):
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=2000)
    duration_minutes: int = Field(ge=5, le=480)
    price: Optional[Decimal] = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    specialization_id: Optional[str] = Field(default=None, max_length=36)
    is_active: bool = True


class ScheduleIn(Strict):
    weekday: int = Field(ge=0, le=6)
    start_time: time
    end_time: time


class ProviderIn(Strict):
    name: str = Field(min_length=2, max_length=120)
    title: str = Field(default="", max_length=120)
    bio: str = Field(default="", max_length=2000)
    specialization_id: Optional[str] = Field(default=None, max_length=36)
    token_prefix: str = Field(pattern=r"^[A-Z0-9]{1,8}$")
    is_active: bool = True
    offering_ids: list[str] = Field(default_factory=list, max_length=100)
    schedules: list[ScheduleIn] = Field(default_factory=list, max_length=50)


class RoomTypeIn(Strict):
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=2000)
    amenities: str = Field(default="", max_length=500)
    max_occupancy: int = Field(ge=1, le=12)
    nightly_rate: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    total_rooms: int = Field(ge=0, le=10000)
    is_active: bool = True


class StaffAssignment(Strict):
    user_id: str = Field(max_length=36)


class RoleUpdate(Strict):
    role: str = Field(pattern="^(CUSTOMER|STAFF|ADMIN)$")
    is_active: Optional[bool] = None
