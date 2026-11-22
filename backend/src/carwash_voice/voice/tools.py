"""Agent tools (section 4.5): schemas plus handlers that call the domain services.

The tool bodies are plain synchronous functions `(session, state, args) -> dict` so they are
easy to test; the async wrappers run them in a worker thread so audio never stalls. Results
are short and speakable. Expected problems (bad input, not found) come back as {"error": ...}
so the agent can say something sensible instead of the call failing.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from loguru import logger
from pipecat.adapters.llm.schemas.function_schema import FunctionSchema
from pipecat.adapters.llm.schemas.tools_schema import ToolsSchema
from pipecat.services.llm_service import FunctionCallParams
from sqlalchemy.orm import Session, sessionmaker

from carwash_voice.db.models import (
    CreatedVia,
    Customer,
    JobStatus,
    Ticket,
    TicketCategory,
    TicketStatus,
)
from carwash_voice.db.session import run_db
from carwash_voice.domain import customers, outbound, tickets
from carwash_voice.domain.errors import DomainError, NotFoundError
from carwash_voice.domain.phone import normalize_phone, normalize_registration
from carwash_voice.voice.session import CallContext, CallHandle

SPOKEN_STATUS = {
    TicketStatus.OPEN: "open and waiting to be picked up",
    TicketStatus.IN_PROGRESS: "being worked on",
    TicketStatus.CALLBACK_REQUESTED: "waiting for a call back from our team",
    TicketStatus.RESOLVED: "resolved",
    TicketStatus.CLOSED: "closed",
}

OUTBOUND_OUTCOMES = ("delivered", "call_back_later", "declined")


# One reply for "not found" and "not confirmed", so callers can't probe which tickets or phone
# numbers exist.
PRIVACY_ERROR = (
    "No ticket found for this caller with those details. Ask the caller to check the ticket "
    "number and for the car registration number on the ticket, then call this tool again with "
    "car_registration."
)


@dataclass
class ToolState:
    call: CallContext
    handle: CallHandle
    customer_id: int | None = None
    verified: set[int] = field(default_factory=set)  # customers confirmed as this caller


# --- privacy -----------------------------------------------------------------------------------
# A customer's details are shared only with someone who is plausibly that customer: the call
# comes from the customer's own number, or the caller gives a second matching detail (the car
# registration) on top of the ticket number or phone number. Five-digit ticket numbers and car
# plates are easy to guess or see, so neither is enough on its own.


def _phone(raw: str | None) -> str | None:
    try:
        return normalize_phone(raw)
    except DomainError:
        return None


def _is_callers(state: ToolState, customer: Customer) -> bool:
    caller = _phone(state.call.caller_number)
    return bool(caller and customer.phone == caller)


def _reg_matches(customer: Customer, args: dict[str, Any]) -> bool:
    reg = normalize_registration(args.get("car_registration"))
    return bool(reg and customer.car_registration == reg)


def _verify(state: ToolState, customer: Customer, second_factor: bool) -> bool:
    if second_factor or customer.id in state.verified or _is_callers(state, customer):
        state.verified.add(customer.id)
        return True
    return False


def _spoken_ref(ref: str) -> str:
    """CW-24871 -> 'C W 2 4 8 7 1' so the agent can say it clearly."""
    return " ".join(ref.replace("-", ""))


def _ticket_summary(t: Ticket) -> dict[str, Any]:
    return {
        "ticket_ref": t.public_ref,
        "category": t.category.value,
        "status": SPOKEN_STATUS[t.status],
        "about": t.description[:120],
        "last_updated": t.updated_at.strftime("%d %b %Y"),
    }


# --- tool bodies ---------------------------------------------------------------------------


def find_customer(session: Session, state: ToolState, args: dict[str, Any]) -> dict[str, Any]:
    said_phone = args.get("phone")
    customer = customers.find_customer(
        session,
        phone=said_phone or state.call.caller_number,
        car_registration=args.get("car_registration"),
    )
    if customer is None:
        return {"found": False}
    said = _phone(said_phone)
    two_details = bool(said and customer.phone == said and _reg_matches(customer, args))
    if not _verify(state, customer, two_details):
        return {
            "found": False,
            "note": (
                "No record confirmed for this caller. Do not share any details; ask for their "
                "name and save them with upsert_customer."
            ),
        }
    state.customer_id = customer.id
    open_refs = [t.public_ref for t in tickets.latest_open_for_phone(session, customer.phone or "")]
    return {
        "found": True,
        "customer_id": customer.id,
        "name": customer.name,
        "car_registration": customer.car_registration,
        "open_tickets": open_refs,
    }


def upsert_customer(session: Session, state: ToolState, args: dict[str, Any]) -> dict[str, Any]:
    """Update the caller's own record, or create a new one. Never attaches to someone else's.

    The caller's own record is the one already confirmed in this call, or the one with the
    caller's phone number. A phone number or registration the caller only *says* never selects
    an existing record: anything else becomes a new customer.
    """
    name, reg = args.get("name"), args.get("car_registration")
    language = args.get("preferred_language")
    caller = _phone(state.call.caller_number)
    customer = None
    if state.customer_id is not None and state.customer_id in state.verified:
        customer = customers.get_customer(session, state.customer_id)
    elif caller:
        customer = customers.find_customer(session, phone=caller)
    if customer is not None:
        customers.update_customer(
            session, customer, name=name, car_registration=reg, preferred_language=language
        )
    else:
        phone = caller or _phone(args.get("phone"))
        if phone and customers.find_customer(session, phone=phone) is not None:
            phone = None  # that number belongs to another customer: don't take it over
        customer = customers.create_customer(
            session, name=name, phone=phone, car_registration=reg, preferred_language=language
        )
    state.customer_id = customer.id
    state.verified.add(customer.id)
    return {"customer_id": customer.id, "name": customer.name, "phone": customer.phone}


def create_ticket(session: Session, state: ToolState, args: dict[str, Any]) -> dict[str, Any]:
    customer_id = state.customer_id
    given = args.get("customer_id")
    if given is not None and int(given) in state.verified:
        customer_id = int(given)
    if customer_id is None:
        return {"error": "Save the customer first with upsert_customer."}
    via = (
        CreatedVia.PHONE_OUTBOUND
        if state.call.direction == "outbound"
        else CreatedVia.PHONE_INBOUND
    )
    ticket = tickets.create_ticket(
        session,
        customer_id=customer_id,
        category=args.get("category", ""),
        description=args.get("description", ""),
        wash_location=args.get("wash_location"),
        wash_date=args.get("wash_date"),
        created_via=via,
    )
    state.handle.ticket_id = ticket.id
    return {"ticket_ref": ticket.public_ref, "say_it_as": _spoken_ref(ticket.public_ref)}


def _confirmed_ticket(session: Session, state: ToolState, args: dict[str, Any]) -> Ticket | None:
    """The ticket named in args if the caller may use it; None if missing or not confirmed."""
    try:
        ticket = tickets.get_ticket(session, args.get("public_ref", ""))
    except NotFoundError:
        return None
    if not _verify(state, ticket.customer, _reg_matches(ticket.customer, args)):
        return None
    return ticket


def get_ticket_status(session: Session, state: ToolState, args: dict[str, Any]) -> dict[str, Any]:
    ref = args.get("public_ref")
    if ref:
        ticket = _confirmed_ticket(session, state, args)
        if ticket is None:
            return {"error": PRIVACY_ERROR}
        state.handle.ticket_id = state.handle.ticket_id or ticket.id
        return _ticket_summary(ticket)
    phone = args.get("phone") or state.call.caller_number
    if not phone:
        return {"error": "Ask the customer for a ticket number or a phone number."}
    customer = customers.find_customer(session, phone=phone)
    if customer is None or not _verify(state, customer, _reg_matches(customer, args)):
        return {"error": PRIVACY_ERROR}
    found = tickets.latest_open_for_phone(session, phone)
    if not found:
        return {"tickets": [], "note": "No open tickets for this phone number."}
    return {"tickets": [_ticket_summary(t) for t in found]}


def add_ticket_note(session: Session, state: ToolState, args: dict[str, Any]) -> dict[str, Any]:
    ticket = _confirmed_ticket(session, state, args)
    if ticket is None:
        return {"error": PRIVACY_ERROR}
    tickets.add_note(session, ticket, args.get("note", ""))
    return {"ok": True, "ticket_ref": ticket.public_ref}


def request_human_callback(
    session: Session, state: ToolState, args: dict[str, Any]
) -> dict[str, Any]:
    ticket = _confirmed_ticket(session, state, args)
    if ticket is None:
        return {"error": PRIVACY_ERROR}
    tickets.request_callback(
        session,
        ticket,
        args.get("reason") or "Customer asked for a person",
        args.get("preferred_time"),
    )
    state.handle.ticket_id = state.handle.ticket_id or ticket.id
    return {"ok": True, "ticket_ref": ticket.public_ref, "message": "A team member will call back."}


def complete_outbound_job(
    session: Session, state: ToolState, args: dict[str, Any]
) -> dict[str, Any]:
    job_id = state.call.outbound_job_id
    if job_id is None:
        return {"error": "This is not an outbound call."}
    outcome = args.get("outcome")
    note = args.get("note")
    if outcome == "delivered":
        status = JobStatus.COMPLETED
    elif outcome == "call_back_later":
        status = JobStatus.QUEUED  # goes back in the queue so staff can call again
    elif outcome == "declined":
        status = JobStatus.FAILED
    else:
        return {"error": f"outcome must be one of {', '.join(OUTBOUND_OUTCOMES)}"}
    outbound.set_job_status(session, job_id, status, note)
    return {"ok": True}


SYNC_TOOLS: dict[str, Callable[[Session, ToolState, dict[str, Any]], dict[str, Any]]] = {
    "find_customer": find_customer,
    "upsert_customer": upsert_customer,
    "create_ticket": create_ticket,
    "get_ticket_status": get_ticket_status,
    "add_ticket_note": add_ticket_note,
    "request_human_callback": request_human_callback,
    "complete_outbound_job": complete_outbound_job,
}

# --- schemas -------------------------------------------------------------------------------

_S = "string"


def tool_schemas(direction: str) -> ToolsSchema:
    """Tool definitions for the model. complete_outbound_job only exists on outbound calls."""
    schemas = [
        FunctionSchema(
            name="find_customer",
            description=(
                "Look up an existing customer by phone number or car registration. If no phone "
                "is given, the caller's number is used."
            ),
            properties={
                "phone": {"type": _S, "description": "Phone number, any format"},
                "car_registration": {"type": _S, "description": "Car registration number"},
            },
            required=[],
        ),
        FunctionSchema(
            name="upsert_customer",
            description=(
                "Create or update the customer record. Call this before create_ticket. If no "
                "phone is given, the caller's number is used."
            ),
            properties={
                "name": {"type": _S},
                "phone": {"type": _S},
                "car_registration": {"type": _S},
                "preferred_language": {"type": _S, "description": "e.g. English, Kannada, Hindi"},
            },
            required=["name"],
        ),
        FunctionSchema(
            name="create_ticket",
            description="Create a complaint ticket. Returns the ticket number to read back.",
            properties={
                "customer_id": {"type": "integer", "description": "From upsert_customer"},
                "category": {"type": _S, "enum": [c.value for c in TicketCategory]},
                "description": {"type": _S, "description": "What went wrong, in English"},
                "wash_location": {"type": _S},
                "wash_date": {"type": _S, "description": "Date of the visit as the customer said"},
            },
            required=["category", "description"],
        ),
        FunctionSchema(
            name="get_ticket_status",
            description=(
                "Get the status of a ticket by its number, or the latest open tickets for a phone "
                "number (the caller's number if none is given)."
            ),
            properties={
                "public_ref": {"type": _S, "description": "Ticket number like CW-24871"},
                "phone": {"type": _S},
                "car_registration": {
                    "type": _S,
                    "description": "Needed if the call is not from the customer's number",
                },
            },
            required=[],
        ),
        FunctionSchema(
            name="add_ticket_note",
            description="Add extra details the customer gave later to an existing ticket.",
            properties={
                "public_ref": {"type": _S},
                "note": {"type": _S},
                "car_registration": {
                    "type": _S,
                    "description": "Needed if the call is not from the customer's number",
                },
            },
            required=["public_ref", "note"],
        ),
        FunctionSchema(
            name="request_human_callback",
            description=(
                "The customer wants a person. Flag the ticket so a team member calls back. "
                "Needs a ticket number (create one first if there is none)."
            ),
            properties={
                "public_ref": {"type": _S},
                "reason": {"type": _S},
                "preferred_time": {"type": _S, "description": "When they would like the call"},
                "car_registration": {
                    "type": _S,
                    "description": "Needed if the call is not from the customer's number",
                },
            },
            required=["public_ref", "reason"],
        ),
        FunctionSchema(
            name="end_call",
            description=(
                "Finish the call. Say your goodbye in the same turn first; the call ends after "
                "your goodbye has been spoken."
            ),
            properties={"reason": {"type": _S, "description": "Why the call is ending"}},
            required=["reason"],
        ),
    ]
    if direction == "outbound":
        schemas.insert(
            -1,
            FunctionSchema(
                name="complete_outbound_job",
                description="Record how the outbound call went. Call it once before end_call.",
                properties={
                    "job_id": {"type": "integer"},
                    "outcome": {"type": _S, "enum": list(OUTBOUND_OUTCOMES)},
                    "note": {"type": _S, "description": "Details, or the callback time"},
                },
                required=["job_id", "outcome"],
            ),
        )
    return ToolsSchema(standard_tools=schemas)


# --- async wrappers for the LLM service ------------------------------------------------------


ToolHandler = Callable[[FunctionCallParams], Awaitable[None]]


def make_handlers(
    session_factory: sessionmaker[Session],
    state: ToolState,
    arm_end_call: Callable[[str], None],
) -> dict[str, ToolHandler]:
    """Async handlers (one per tool) for llm.register_function."""

    def wrap(name: str) -> ToolHandler:
        body = SYNC_TOOLS[name]

        async def handler(params: FunctionCallParams) -> None:
            args = dict(params.arguments or {})
            try:
                result = await run_db(session_factory, body, state, args)
            except DomainError as exc:
                result = {"error": str(exc)}
            except Exception:
                logger.exception("Tool {} failed", name)
                result = {"error": "Something went wrong. Offer a human callback."}
            logger.info("Tool {} -> {}", name, "error" if "error" in result else "ok")
            await params.result_callback(result)

        return handler

    async def end_call(params: FunctionCallParams) -> None:
        reason = str((params.arguments or {}).get("reason") or "agent_done")
        arm_end_call(reason)
        await params.result_callback(
            {
                "ok": True,
                "instruction": (
                    "The call ends when you stop speaking. If you have already said goodbye, "
                    "say nothing more. Otherwise say one short goodbye now."
                ),
            }
        )

    handlers = {name: wrap(name) for name in SYNC_TOOLS}
    handlers["end_call"] = end_call
    return handlers
