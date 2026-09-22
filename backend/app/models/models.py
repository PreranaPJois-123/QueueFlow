import enum
import uuid

from sqlalchemy import (
    Column, String, Boolean, DateTime, ForeignKey, Integer, Enum as SAEnum,
    Text, func, Index, UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


def gen_uuid():
    return str(uuid.uuid4())


# ----------------------------- Enums -----------------------------

class UserRole(str, enum.Enum):
    CUSTOMER = "CUSTOMER"
    STAFF = "STAFF"
    ADMIN = "ADMIN"


class QueueStatus(str, enum.Enum):
    OPEN = "OPEN"
    PAUSED = "PAUSED"
    CLOSED = "CLOSED"


class TicketStatus(str, enum.Enum):
    WAITING = "WAITING"
    CALLED = "CALLED"
    SERVING = "SERVING"
    SERVED = "SERVED"
    SKIPPED = "SKIPPED"
    CANCELLED = "CANCELLED"


class AppointmentStatus(str, enum.Enum):
    SCHEDULED = "SCHEDULED"
    CHECKED_IN = "CHECKED_IN"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    NO_SHOW = "NO_SHOW"


class NotificationType(str, enum.Enum):
    TURN_APPROACHING = "TURN_APPROACHING"
    CALLED = "CALLED"
    QUEUE_UPDATE = "QUEUE_UPDATE"
    SYSTEM = "SYSTEM"


# ----------------------------- Models -----------------------------

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(SAEnum(UserRole, name="user_role"), nullable=False, default=UserRole.CUSTOMER)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    tickets = relationship("Ticket", back_populates="customer", foreign_keys="Ticket.customer_id")
    appointments = relationship("Appointment", back_populates="customer")


class Service(Base):
    __tablename__ = "services"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    queues = relationship("Queue", back_populates="service")


class Queue(Base):
    __tablename__ = "queues"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    service_id = Column(String(36), ForeignKey("services.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    status = Column(SAEnum(QueueStatus, name="queue_status"), nullable=False, default=QueueStatus.OPEN)
    # Next token counter (sequential per queue). Guarded by SELECT ... FOR UPDATE at the row level.
    next_token_number = Column(Integer, nullable=False, default=1)
    current_serving_number = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    service = relationship("Service", back_populates="queues")
    tickets = relationship("Ticket", back_populates="queue")

    __table_args__ = (
        Index("ix_queue_service_status", "service_id", "status"),
    )


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    queue_id = Column(String(36), ForeignKey("queues.id"), nullable=False, index=True)
    customer_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    token_number = Column(Integer, nullable=False)
    token_label = Column(String(16), nullable=False)  # e.g. "A047"
    status = Column(SAEnum(TicketStatus, name="ticket_status"), nullable=False, default=TicketStatus.WAITING)
    called_at = Column(DateTime(timezone=True), nullable=True)
    serving_started_at = Column(DateTime(timezone=True), nullable=True)
    served_at = Column(DateTime(timezone=True), nullable=True)
    skipped_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    queue = relationship("Queue", back_populates="tickets")
    customer = relationship("User", back_populates="tickets", foreign_keys=[customer_id])
    service_record = relationship("ServiceRecord", back_populates="ticket", uselist=False)

    __table_args__ = (
        # A customer may only have ONE active (WAITING/CALLED/SERVING) ticket per queue.
        Index("ix_ticket_queue_status", "queue_id", "status"),
        Index("ix_ticket_customer_status", "customer_id", "status"),
    )


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    customer_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    service_id = Column(String(36), ForeignKey("services.id"), nullable=False, index=True)
    scheduled_time = Column(DateTime(timezone=True), nullable=False)
    status = Column(SAEnum(AppointmentStatus, name="appointment_status"), nullable=False,
                     default=AppointmentStatus.SCHEDULED)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    customer = relationship("User", back_populates="appointments")
    service = relationship("Service")


class ServiceRecord(Base):
    """Historical record of a completed ticket — used to compute average service time."""
    __tablename__ = "service_records"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    ticket_id = Column(String(36), ForeignKey("tickets.id"), nullable=False, unique=True)
    queue_id = Column(String(36), ForeignKey("queues.id"), nullable=False, index=True)
    service_id = Column(String(36), ForeignKey("services.id"), nullable=False, index=True)
    wait_seconds = Column(Integer, nullable=False)      # created_at -> serving_started_at
    service_seconds = Column(Integer, nullable=False)   # serving_started_at -> served_at
    outcome = Column(SAEnum(TicketStatus, name="record_outcome"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    ticket = relationship("Ticket", back_populates="service_record")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    ticket_id = Column(String(36), ForeignKey("tickets.id"), nullable=True)
    type = Column(SAEnum(NotificationType, name="notification_type"), nullable=False)
    message = Column(String(500), nullable=False)
    is_read = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
