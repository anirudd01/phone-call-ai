"""Request and response models for the REST API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from carwash_voice.db.models import (
    Actor,
    CallDirection,
    CreatedVia,
    EventKind,
    JobPurpose,
    JobStatus,
    TicketCategory,
    TicketStatus,
)


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CustomerOut(_Out):
    id: int
    phone: str | None
    name: str | None
    car_registration: str | None
    preferred_language: str | None
    created_at: datetime
    updated_at: datetime


class TicketEventOut(_Out):
    id: int
    kind: EventKind
    detail: str | None
    actor: Actor
    created_at: datetime


class TicketOut(_Out):
    id: int
    public_ref: str
    customer_id: int
    category: TicketCategory
    description: str
    wash_location: str | None
    wash_date: str | None
    status: TicketStatus
    priority: str
    created_via: CreatedVia
    created_at: datetime
    updated_at: datetime


class TicketDetailOut(TicketOut):
    events: list[TicketEventOut]


class TicketPatch(BaseModel):
    status: TicketStatus | None = None
    priority: str | None = None
    note: str | None = None


class CallOut(_Out):
    id: str
    direction: CallDirection
    caller_number: str | None
    started_at: datetime
    ended_at: datetime | None
    end_reason: str | None
    language_detected: str | None
    ticket_id: int | None
    outbound_job_id: int | None
    audio_path: str | None
    transcript: list[dict[str, Any]]
    summary: str | None


class OutboundJobIn(BaseModel):
    message: str
    ticket_ref: str | None = None
    customer_id: int | None = None
    purpose: JobPurpose = JobPurpose.TICKET_UPDATE


class OutboundJobOut(_Out):
    id: int
    customer_id: int
    ticket_id: int | None
    phone: str
    purpose: JobPurpose
    message: str
    status: JobStatus
    outcome_note: str | None
    created_at: datetime
    updated_at: datetime


class JobStatusIn(BaseModel):
    status: JobStatus
    outcome_note: str | None = None
