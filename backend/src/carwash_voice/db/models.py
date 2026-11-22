"""SQLAlchemy 2 models (section 4.4). Portable across SQLite and Postgres."""

from __future__ import annotations

import enum
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _now() -> datetime:
    return datetime.now(UTC)


def _enum(cls: type[enum.Enum]) -> Enum:
    """String-backed enum without native DB enum types or CHECK constraints."""
    return Enum(
        cls,
        native_enum=False,
        create_constraint=False,
        length=32,
        values_callable=lambda e: [m.value for m in e],
    )


class TicketCategory(enum.StrEnum):
    QUALITY = "quality"
    DAMAGE = "damage"
    BILLING = "billing"
    BOOKING = "booking"
    OTHER = "other"


class TicketStatus(enum.StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    CALLBACK_REQUESTED = "callback_requested"
    RESOLVED = "resolved"
    CLOSED = "closed"


class CreatedVia(enum.StrEnum):
    PHONE_INBOUND = "phone_inbound"
    PHONE_OUTBOUND = "phone_outbound"
    API = "api"


class EventKind(enum.StrEnum):
    CREATED = "created"
    STATUS_CHANGED = "status_changed"
    NOTE = "note"
    CALLBACK_REQUESTED = "callback_requested"
    CUSTOMER_UPDATED = "customer_updated"


class Actor(enum.StrEnum):
    AGENT = "agent"
    STAFF = "staff"


class CallDirection(enum.StrEnum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class JobPurpose(enum.StrEnum):
    TICKET_UPDATE = "ticket_update"
    FOLLOW_UP = "follow_up"


class JobStatus(enum.StrEnum):
    QUEUED = "queued"
    DIALLING = "dialling"
    COMPLETED = "completed"
    NO_ANSWER = "no_answer"
    FAILED = "failed"


class Base(DeclarativeBase):
    pass


def _ts() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), default=_now)


def _ts_updated() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    phone: Mapped[str | None] = mapped_column(String(20), unique=True)  # E.164
    name: Mapped[str | None] = mapped_column(String(200))
    car_registration: Mapped[str | None] = mapped_column(String(20))
    preferred_language: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = _ts()
    updated_at: Mapped[datetime] = _ts_updated()

    tickets: Mapped[list[Ticket]] = relationship(back_populates="customer")


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_ref: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    category: Mapped[TicketCategory] = mapped_column(_enum(TicketCategory))
    description: Mapped[str] = mapped_column(Text)
    wash_location: Mapped[str | None] = mapped_column(String(200))
    wash_date: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[TicketStatus] = mapped_column(_enum(TicketStatus), default=TicketStatus.OPEN)
    priority: Mapped[str] = mapped_column(String(16), default="normal")
    created_via: Mapped[CreatedVia] = mapped_column(_enum(CreatedVia))
    created_at: Mapped[datetime] = _ts()
    updated_at: Mapped[datetime] = _ts_updated()

    customer: Mapped[Customer] = relationship(back_populates="tickets")
    events: Mapped[list[TicketEvent]] = relationship(
        back_populates="ticket", order_by="TicketEvent.id"
    )


class TicketEvent(Base):
    __tablename__ = "ticket_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"), index=True)
    kind: Mapped[EventKind] = mapped_column(_enum(EventKind))
    detail: Mapped[str | None] = mapped_column(Text)
    actor: Mapped[Actor] = mapped_column(_enum(Actor))
    created_at: Mapped[datetime] = _ts()

    ticket: Mapped[Ticket] = relationship(back_populates="events")


class OutboundJob(Base):
    __tablename__ = "outbound_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    ticket_id: Mapped[int | None] = mapped_column(ForeignKey("tickets.id"))
    phone: Mapped[str] = mapped_column(String(20))
    purpose: Mapped[JobPurpose] = mapped_column(_enum(JobPurpose))
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[JobStatus] = mapped_column(_enum(JobStatus), default=JobStatus.QUEUED)
    outcome_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _ts()
    updated_at: Mapped[datetime] = _ts_updated()


class Call(Base):
    __tablename__ = "calls"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # call_id uuid4
    direction: Mapped[CallDirection] = mapped_column(_enum(CallDirection))
    caller_number: Mapped[str | None] = mapped_column(String(20))
    started_at: Mapped[datetime] = _ts()
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_reason: Mapped[str | None] = mapped_column(String(64))
    language_detected: Mapped[str | None] = mapped_column(String(20))
    ticket_id: Mapped[int | None] = mapped_column(ForeignKey("tickets.id"))
    outbound_job_id: Mapped[int | None] = mapped_column(ForeignKey("outbound_jobs.id"))
    audio_path: Mapped[str | None] = mapped_column(String(500))
    transcript: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    summary: Mapped[str | None] = mapped_column(Text)
