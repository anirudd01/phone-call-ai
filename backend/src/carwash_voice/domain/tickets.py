"""Ticket service: creation, status, notes, callbacks and events."""

from __future__ import annotations

import secrets

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from carwash_voice.db.models import (
    Actor,
    CreatedVia,
    Customer,
    EventKind,
    Ticket,
    TicketCategory,
    TicketEvent,
    TicketStatus,
)
from carwash_voice.domain.customers import get_customer
from carwash_voice.domain.errors import InvalidInputError, NotFoundError
from carwash_voice.domain.phone import normalize_phone

REF_PREFIX = "CW-"
OPEN_STATUSES = (TicketStatus.OPEN, TicketStatus.IN_PROGRESS, TicketStatus.CALLBACK_REQUESTED)


def _new_ref() -> str:
    """Short and easy to say aloud: CW- plus five digits, never starting with 0."""
    return f"{REF_PREFIX}{secrets.randbelow(90000) + 10000}"


def _add_event(
    session: Session, ticket: Ticket, kind: EventKind, detail: str | None, actor: Actor
) -> TicketEvent:
    event = TicketEvent(ticket_id=ticket.id, kind=kind, detail=detail, actor=actor)
    session.add(event)
    return event


def normalize_ref(raw: str) -> str:
    """Accept 'cw 24871', 'CW-24871' or '24871'."""
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) != 5:
        raise InvalidInputError(f"'{raw}' is not a valid ticket number")
    return f"{REF_PREFIX}{digits}"


def get_ticket(session: Session, public_ref: str) -> Ticket:
    ticket = session.scalar(select(Ticket).where(Ticket.public_ref == normalize_ref(public_ref)))
    if ticket is None:
        raise NotFoundError(f"Ticket {public_ref} not found")
    return ticket


def create_ticket(
    session: Session,
    customer_id: int,
    category: TicketCategory | str,
    description: str,
    wash_location: str | None = None,
    wash_date: str | None = None,
    created_via: CreatedVia = CreatedVia.PHONE_INBOUND,
    actor: Actor = Actor.AGENT,
) -> Ticket:
    if not description or not description.strip():
        raise InvalidInputError("A ticket needs a description")
    try:
        category = TicketCategory(category)
    except ValueError as exc:
        raise InvalidInputError(f"Unknown category '{category}'") from exc
    get_customer(session, customer_id)

    for _ in range(20):
        ticket = Ticket(
            public_ref=_new_ref(),
            customer_id=customer_id,
            category=category,
            description=description.strip(),
            wash_location=wash_location,
            wash_date=wash_date,
            created_via=created_via,
        )
        session.add(ticket)
        try:
            session.flush()
        except IntegrityError:  # reference collision: try another
            session.rollback()
            continue
        _add_event(session, ticket, EventKind.CREATED, description.strip(), actor)
        session.commit()
        return ticket
    raise RuntimeError("Could not generate a unique ticket reference")


def update_status(
    session: Session,
    ticket: Ticket,
    status: TicketStatus | str,
    actor: Actor = Actor.STAFF,
    detail: str | None = None,
) -> Ticket:
    try:
        new = TicketStatus(status)
    except ValueError as exc:
        raise InvalidInputError(f"Unknown status '{status}'") from exc
    if new != ticket.status:
        old = ticket.status
        ticket.status = new
        _add_event(
            session,
            ticket,
            EventKind.STATUS_CHANGED,
            f"{old.value} -> {new.value}" + (f": {detail}" if detail else ""),
            actor,
        )
    session.commit()
    return ticket


def add_note(
    session: Session, ticket: Ticket, note: str, actor: Actor = Actor.AGENT
) -> TicketEvent:
    if not note or not note.strip():
        raise InvalidInputError("Note is empty")
    event = _add_event(session, ticket, EventKind.NOTE, note.strip(), actor)
    session.commit()
    return event


def request_callback(
    session: Session,
    ticket: Ticket,
    reason: str,
    preferred_time: str | None = None,
    actor: Actor = Actor.AGENT,
) -> Ticket:
    detail = reason.strip() + (f" (preferred time: {preferred_time})" if preferred_time else "")
    ticket.status = TicketStatus.CALLBACK_REQUESTED
    _add_event(session, ticket, EventKind.CALLBACK_REQUESTED, detail, actor)
    session.commit()
    return ticket


def list_tickets(
    session: Session, status: TicketStatus | str | None = None, limit: int = 100, offset: int = 0
) -> list[Ticket]:
    query = select(Ticket).order_by(Ticket.id.desc()).limit(limit).offset(offset)
    if status:
        try:
            query = query.where(Ticket.status == TicketStatus(status))
        except ValueError as exc:
            raise InvalidInputError(f"Unknown status '{status}'") from exc
    return list(session.scalars(query))


def latest_open_for_phone(session: Session, phone: str, limit: int = 3) -> list[Ticket]:
    """Most recent open tickets for the customer with this phone number."""
    norm = normalize_phone(phone)
    if not norm:
        return []
    query = (
        select(Ticket)
        .join(Customer, Ticket.customer_id == Customer.id)
        .where(Customer.phone == norm, Ticket.status.in_(OPEN_STATUSES))
        .order_by(Ticket.id.desc())
        .limit(limit)
    )
    return list(session.scalars(query))
