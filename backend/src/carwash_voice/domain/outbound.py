"""Outbound update-call jobs."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from carwash_voice.db.models import (
    Actor,
    EventKind,
    JobPurpose,
    JobStatus,
    OutboundJob,
    TicketEvent,
)
from carwash_voice.domain.customers import get_customer
from carwash_voice.domain.errors import InvalidInputError, NotFoundError
from carwash_voice.domain.tickets import get_ticket


def create_job(
    session: Session,
    message: str,
    ticket_ref: str | None = None,
    customer_id: int | None = None,
    purpose: JobPurpose | str = JobPurpose.TICKET_UPDATE,
) -> OutboundJob:
    """Queue a call. Give a ticket (its customer is used) or a customer id."""
    if not message or not message.strip():
        raise InvalidInputError("An outbound job needs a message")
    ticket = get_ticket(session, ticket_ref) if ticket_ref else None
    if ticket is not None:
        customer_id = ticket.customer_id
    if customer_id is None:
        raise InvalidInputError("Give a ticket_ref or a customer_id")
    customer = get_customer(session, customer_id)
    if not customer.phone:
        raise InvalidInputError("The customer has no phone number to call")
    try:
        purpose = JobPurpose(purpose)
    except ValueError as exc:
        raise InvalidInputError(f"Unknown purpose '{purpose}'") from exc
    job = OutboundJob(
        customer_id=customer.id,
        ticket_id=ticket.id if ticket else None,
        phone=customer.phone,
        purpose=purpose,
        message=message.strip(),
    )
    session.add(job)
    session.commit()
    return job


def get_job(session: Session, job_id: int) -> OutboundJob:
    job = session.get(OutboundJob, job_id)
    if job is None:
        raise NotFoundError(f"Outbound job {job_id} not found")
    return job


def list_jobs(
    session: Session, status: JobStatus | str | None = None, limit: int = 100
) -> list[OutboundJob]:
    query = select(OutboundJob).order_by(OutboundJob.id.desc()).limit(limit)
    if status:
        try:
            query = query.where(OutboundJob.status == JobStatus(status))
        except ValueError as exc:
            raise InvalidInputError(f"Unknown status '{status}'") from exc
    return list(session.scalars(query))


def next_queued_job(session: Session) -> OutboundJob | None:
    """Oldest queued job (does not change its status)."""
    return session.scalar(
        select(OutboundJob).where(OutboundJob.status == JobStatus.QUEUED).order_by(OutboundJob.id)
    )


def set_job_status(
    session: Session, job_id: int, status: JobStatus | str, outcome_note: str | None = None
) -> OutboundJob:
    """Change a job's status; terminal outcomes are also written to the ticket's events."""
    job = get_job(session, job_id)
    try:
        job.status = JobStatus(status)
    except ValueError as exc:
        raise InvalidInputError(f"Unknown status '{status}'") from exc
    if outcome_note:
        job.outcome_note = outcome_note
    if job.ticket_id and job.status in (JobStatus.COMPLETED, JobStatus.NO_ANSWER, JobStatus.FAILED):
        detail = f"Outbound call {job.status.value}" + (f": {outcome_note}" if outcome_note else "")
        session.add(
            TicketEvent(
                ticket_id=job.ticket_id, kind=EventKind.NOTE, detail=detail, actor=Actor.AGENT
            )
        )
    session.commit()
    return job
