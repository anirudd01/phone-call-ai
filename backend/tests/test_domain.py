import pytest
from sqlalchemy.orm import Session

from carwash_voice.db.models import CallDirection, EventKind, JobStatus, TicketStatus
from carwash_voice.domain import calls, customers, outbound, tickets
from carwash_voice.domain.errors import InvalidInputError, NotFoundError
from carwash_voice.domain.phone import normalize_phone, normalize_registration


def _customer(session: Session, phone: str | None = "98450 12345"):
    return customers.upsert_customer(
        session, name="Ravi", phone=phone, car_registration="ka 01 ab 1234"
    )


# --- phone -------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw", ["9845012345", "98450 12345", "+91 98450 12345", "09845012345", "+919845012345"]
)
def test_phone_normalised_to_e164(raw: str) -> None:
    assert normalize_phone(raw) == "+919845012345"


def test_blank_phone_is_none() -> None:
    assert normalize_phone("  ") is None
    assert normalize_phone(None) is None


@pytest.mark.parametrize("raw", ["12345", "abc"])
def test_invalid_phone_rejected(raw: str) -> None:
    with pytest.raises(InvalidInputError):
        normalize_phone(raw)


def test_registration_normalised() -> None:
    assert normalize_registration("ka 01-ab 1234") == "KA01AB1234"
    assert normalize_registration("  ") is None


# --- customers ---------------------------------------------------------------


def test_upsert_creates_then_updates_by_phone(session: Session) -> None:
    first = _customer(session)
    again = customers.upsert_customer(session, phone="+919845012345", preferred_language="kn")
    assert again.id == first.id
    assert again.name == "Ravi"  # not overwritten by a missing value
    assert again.preferred_language == "kn"


def test_find_by_registration_and_phone(session: Session) -> None:
    c = _customer(session)
    assert customers.find_customer(session, car_registration="KA01 AB1234").id == c.id
    assert customers.find_customer(session, phone="9845012345").id == c.id
    assert customers.find_customer(session, phone="9000000000") is None


def test_upsert_needs_something(session: Session) -> None:
    with pytest.raises(InvalidInputError):
        customers.upsert_customer(session)


def test_get_customer_missing(session: Session) -> None:
    with pytest.raises(NotFoundError):
        customers.get_customer(session, 999)


# --- tickets -----------------------------------------------------------------


def test_create_ticket_has_short_ref_and_created_event(session: Session) -> None:
    c = _customer(session)
    t = tickets.create_ticket(session, c.id, "quality", "Dirty seats", wash_location="Indiranagar")
    assert t.public_ref.startswith("CW-") and len(t.public_ref) == 8
    assert t.status == TicketStatus.OPEN
    assert [e.kind for e in t.events] == [EventKind.CREATED]


def test_ticket_refs_unique(session: Session) -> None:
    c = _customer(session)
    refs = {
        tickets.create_ticket(session, c.id, "other", f"issue {i}").public_ref for i in range(30)
    }
    assert len(refs) == 30


def test_create_ticket_validation(session: Session) -> None:
    c = _customer(session)
    with pytest.raises(InvalidInputError):
        tickets.create_ticket(session, c.id, "nonsense", "x")
    with pytest.raises(InvalidInputError):
        tickets.create_ticket(session, c.id, "quality", "  ")
    with pytest.raises(NotFoundError):
        tickets.create_ticket(session, 999, "quality", "x")


def test_get_ticket_accepts_spoken_forms(session: Session) -> None:
    c = _customer(session)
    t = tickets.create_ticket(session, c.id, "quality", "x")
    digits = t.public_ref[3:]
    for form in (t.public_ref, t.public_ref.lower(), f"cw {digits}", digits):
        assert tickets.get_ticket(session, form).id == t.id
    with pytest.raises(NotFoundError):
        tickets.get_ticket(session, "CW-00000")
    with pytest.raises(InvalidInputError):
        tickets.get_ticket(session, "banana")


def test_status_change_writes_event(session: Session) -> None:
    c = _customer(session)
    t = tickets.create_ticket(session, c.id, "quality", "x")
    tickets.update_status(session, t, "resolved", detail="refund done")
    assert t.status == TicketStatus.RESOLVED
    assert t.events[-1].kind == EventKind.STATUS_CHANGED
    assert "open -> resolved" in t.events[-1].detail
    count = len(t.events)
    tickets.update_status(session, t, "resolved")  # no change, no new event
    assert len(t.events) == count
    with pytest.raises(InvalidInputError):
        tickets.update_status(session, t, "bogus")


def test_note_and_callback(session: Session) -> None:
    c = _customer(session)
    t = tickets.create_ticket(session, c.id, "billing", "overcharged")
    tickets.add_note(session, t, "Car is a white Swift")
    tickets.request_callback(session, t, "wants a manager", preferred_time="evening")
    assert t.status == TicketStatus.CALLBACK_REQUESTED
    assert t.events[-1].kind == EventKind.CALLBACK_REQUESTED
    assert "evening" in t.events[-1].detail
    with pytest.raises(InvalidInputError):
        tickets.add_note(session, t, " ")


def test_list_and_latest_open(session: Session) -> None:
    c = _customer(session)
    a = tickets.create_ticket(session, c.id, "quality", "a")
    b = tickets.create_ticket(session, c.id, "damage", "b")
    tickets.update_status(session, a, "closed")
    assert [t.id for t in tickets.list_tickets(session)] == [b.id, a.id]
    assert [t.id for t in tickets.list_tickets(session, status="closed")] == [a.id]
    assert [t.id for t in tickets.latest_open_for_phone(session, "9845012345")] == [b.id]
    assert tickets.latest_open_for_phone(session, "9000000000") == []
    with pytest.raises(InvalidInputError):
        tickets.list_tickets(session, status="bogus")


# --- calls -------------------------------------------------------------------


def test_call_lifecycle_and_double_finalize(session: Session) -> None:
    call = calls.create_call(session, "11111111-1111-4111-8111-111111111111", "inbound", "bad")
    assert call.caller_number is None  # invalid caller id is dropped, call still recorded
    assert call.direction == CallDirection.INBOUND
    calls.finalize_call(session, call.id, "operator_hangup", transcript=[{"role": "user"}])
    first_end = call.ended_at
    calls.finalize_call(session, call.id, "error")
    assert call.end_reason == "operator_hangup" and call.ended_at == first_end
    assert calls.list_calls(session)[0].id == call.id
    with pytest.raises(NotFoundError):
        calls.get_call(session, "nope")


# --- outbound ----------------------------------------------------------------


def test_outbound_job_flow(session: Session) -> None:
    c = _customer(session)
    t = tickets.create_ticket(session, c.id, "billing", "refund?")
    job = outbound.create_job(session, "Your refund is approved", ticket_ref=t.public_ref)
    assert job.phone == "+919845012345" and job.ticket_id == t.id
    assert outbound.next_queued_job(session).id == job.id
    outbound.set_job_status(session, job.id, "dialling")
    assert outbound.next_queued_job(session) is None
    outbound.set_job_status(session, job.id, "completed", "customer happy")
    assert job.status == JobStatus.COMPLETED
    assert "customer happy" in t.events[-1].detail
    assert outbound.list_jobs(session, status="completed")[0].id == job.id


def test_outbound_job_validation(session: Session) -> None:
    no_phone = customers.upsert_customer(session, name="NoPhone")
    with pytest.raises(InvalidInputError):
        outbound.create_job(session, "hi", customer_id=no_phone.id)
    with pytest.raises(InvalidInputError):
        outbound.create_job(session, " ", customer_id=no_phone.id)
    with pytest.raises(InvalidInputError):
        outbound.create_job(session, "hi")
    with pytest.raises(NotFoundError):
        outbound.get_job(session, 999)
