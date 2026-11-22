"""Call records: create at start, finalise at end (always)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from carwash_voice.db.models import Call, CallDirection
from carwash_voice.domain.errors import NotFoundError
from carwash_voice.domain.phone import normalize_phone


def create_call(
    session: Session,
    call_id: str,
    direction: CallDirection | str,
    caller_number: str | None = None,
    outbound_job_id: int | None = None,
) -> Call:
    try:
        number = normalize_phone(caller_number)
    except Exception:  # a bad caller id must never stop a call from being recorded
        number = None
    call = Call(
        id=call_id,
        direction=CallDirection(direction),
        caller_number=number,
        outbound_job_id=outbound_job_id,
        transcript=[],
    )
    session.add(call)
    session.commit()
    return call


def get_call(session: Session, call_id: str) -> Call:
    call = session.get(Call, call_id)
    if call is None:
        raise NotFoundError(f"Call {call_id} not found")
    return call


def finalize_call(
    session: Session,
    call_id: str,
    end_reason: str,
    transcript: list[dict[str, Any]] | None = None,
    audio_path: str | None = None,
    language_detected: str | None = None,
    ticket_id: int | None = None,
) -> Call:
    """Set the end time and reason; safe to call twice (the first end time is kept)."""
    call = get_call(session, call_id)
    if call.ended_at is None:
        call.ended_at = datetime.now(UTC)
        call.end_reason = end_reason
    if transcript is not None:
        call.transcript = transcript
    if audio_path is not None:
        call.audio_path = audio_path
    if language_detected is not None:
        call.language_detected = language_detected
    if ticket_id is not None:
        call.ticket_id = ticket_id
    session.commit()
    return call


def list_calls(session: Session, limit: int = 50, offset: int = 0) -> list[Call]:
    query = select(Call).order_by(Call.started_at.desc()).limit(limit).offset(offset)
    return list(session.scalars(query))
