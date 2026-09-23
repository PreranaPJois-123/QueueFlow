from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator

from app.models.models import UserRole, QueueStatus, TicketStatus, AppointmentStatus, NotificationType


# ----------------------------- Auth -----------------------------

class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)  # 72 bytes is bcrypt's hard limit
    full_name: str = Field(min_length=1, max_length=255)
    role: UserRole = UserRole.CUSTOMER

    @field_validator("password")
    @classmethod
    def password_bytes(cls, value):
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 UTF-8 bytes")
        return value


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime


# ----------------------------- Service -----------------------------

class ServiceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None


class ServiceUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    is_active: Optional[bool] = None


class ServiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    description: Optional[str]
    is_active: bool
    created_at: datetime


# ----------------------------- Queue -----------------------------

class QueueCreate(BaseModel):
    service_id: str
    name: str = Field(min_length=1, max_length=255)


class QueueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    service_id: str
    name: str
    status: QueueStatus
    current_serving_number: Optional[int]
    created_at: datetime


class QueueStateOut(BaseModel):
    """Rich real-time state used by both the staff dashboard and WebSocket pushes."""
    queue_id: str
    queue_name: str
    status: QueueStatus
    current_serving_label: Optional[str] = None
    now_serving_ticket_id: Optional[str] = None
    next_ticket_label: Optional[str] = None
    waiting_labels: list[str] = []
    waiting_count: int = 0


# ----------------------------- Ticket -----------------------------

class TicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    queue_id: str
    customer_id: str
    token_number: int
    token_label: str
    status: TicketStatus
    created_at: datetime
    called_at: Optional[datetime] = None
    serving_started_at: Optional[datetime] = None
    served_at: Optional[datetime] = None


class TicketDetailOut(BaseModel):
    ticket: TicketOut
    people_ahead: int
    estimated_wait_minutes: int
    current_serving_label: Optional[str] = None
    queue_status: QueueStatus
    smart_alert: bool = False


# ----------------------------- Appointment -----------------------------

class AppointmentCreate(BaseModel):
    service_id: str
    scheduled_time: datetime
    notes: Optional[str] = None


class AppointmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    service_id: str
    scheduled_time: datetime
    status: AppointmentStatus
    notes: Optional[str]
    created_at: datetime


# ----------------------------- Analytics -----------------------------

class AnalyticsOut(BaseModel):
    customers_served_today: int
    average_wait_minutes: float
    average_service_minutes: float
    active_queues: int
    completed_tickets_today: int
    skipped_tickets_today: int
    busiest_hour: Optional[int] = None


# ----------------------------- Notifications -----------------------------

class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    type: NotificationType
    message: str
    is_read: bool
    created_at: datetime


# ----------------------------- Errors -----------------------------

class ErrorResponse(BaseModel):
    detail: str
