from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator, model_validator

from app.models.models import UserRole, QueueStatus, TicketStatus, AppointmentStatus, NotificationType


class NamedInput(BaseModel):
    @field_validator("full_name", "name", check_fields=False)
    @classmethod
    def trim_name(cls, value):
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be blank")
        return value


# ----------------------------- Auth -----------------------------

COMMON_PASSWORDS = {
    "password", "password1", "password123", "1234567890", "qwertyuiop", "letmein123", "welcome123",
    "iloveyou12", "admin12345", "queueflow1", "qwerty1234", "abc1234567",
}


def check_password_strength(password: str, email: str | None = None) -> str:
    """Policy: 10-128 characters, at least one letter and one digit, not a
    common password, and not derived from the email address."""
    if not 10 <= len(password) <= 128:
        raise ValueError("Password must be between 10 and 128 characters")
    if not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
        raise ValueError("Password must contain at least one letter and one number")
    if password.lower() in COMMON_PASSWORDS:
        raise ValueError("This password is too common; choose another")
    if email and email.split("@")[0].lower() in password.lower() and len(email.split("@")[0]) >= 4:
        raise ValueError("Password must not contain your email name")
    return password


class AccountCreate(NamedInput):
    """Trusted account creation (CLI/admin bootstrap)."""
    email: EmailStr
    password: str
    full_name: str = Field(min_length=1, max_length=255)

    @model_validator(mode="after")
    def strong_password(self):
        check_password_strength(self.password, self.email)
        return self


class UserRegister(NamedInput):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str = Field(max_length=128)
    confirm_password: str = Field(max_length=128)
    full_name: str = Field(min_length=1, max_length=120)
    # Accepted only so an escalation attempt can be rejected explicitly (403).
    role: Optional[UserRole] = None

    @model_validator(mode="after")
    def passwords(self):
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        check_password_strength(self.password, self.email)
        return self


class UserLogin(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str = Field(max_length=128)


class PasswordChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(max_length=128)
    new_password: str = Field(max_length=128)
    confirm_password: str = Field(max_length=128)

    @model_validator(mode="after")
    def passwords(self):
        if self.new_password != self.confirm_password:
            raise ValueError("Passwords do not match")
        check_password_strength(self.new_password)
        return self


class PasswordResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=20, max_length=128)
    new_password: str = Field(max_length=128)
    confirm_password: str = Field(max_length=128)

    @model_validator(mode="after")
    def passwords(self):
        if self.new_password != self.confirm_password:
            raise ValueError("Passwords do not match")
        check_password_strength(self.new_password)
        return self


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    pref_sound_enabled: bool = False
    pref_browser_enabled: bool = False
    created_at: datetime


class SessionOut(BaseModel):
    user: UserOut
    csrf_token: str


# ----------------------------- Service -----------------------------

class ServiceCreate(NamedInput):
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=5000)


class ServiceUpdate(NamedInput):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=5000)
    is_active: Optional[bool] = None


class ServiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    description: Optional[str]
    is_active: bool
    created_at: datetime


# ----------------------------- Queue -----------------------------

class QueueCreate(NamedInput):
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
    queue_name: str = ""
    service_name: str = ""
    prediction_source: str = "calculated_default"
    prediction_samples: int = 0
    estimated_service_minutes: float = 5


# ----------------------------- Appointment -----------------------------

class AppointmentCreate(BaseModel):
    service_id: str
    scheduled_time: datetime
    notes: Optional[str] = Field(default=None, max_length=2000)


class AppointmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    service_id: str
    scheduled_time: datetime
    status: AppointmentStatus
    notes: Optional[str]
    created_at: datetime


class StaffAppointmentOut(AppointmentOut):
    customer_name: str
    service_name: str


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


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    pref_sound_enabled: Optional[bool] = None
    pref_browser_enabled: Optional[bool] = None

    @field_validator("full_name")
    @classmethod
    def clean_name(cls, value):
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be blank")
        return value
