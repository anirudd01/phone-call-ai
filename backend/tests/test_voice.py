import asyncio
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    ClientConnectedFrame,
    LLMRunFrame,
)
from pipecat.tests.utils import SleepFrame, run_test
from sqlalchemy.orm import Session

from carwash_voice.config import ConfigError, Settings
from carwash_voice.db.models import JobStatus, TicketStatus
from carwash_voice.domain import customers, outbound, tickets
from carwash_voice.voice import tools
from carwash_voice.voice.processors import EndCallWatcher, GreetOnConnect
from carwash_voice.voice.prompts import OutboundBrief, build_system_prompt, greeting_trigger
from carwash_voice.voice.providers.openai_realtime import OpenAIRealtimeProvider
from carwash_voice.voice.session import CallContext, CallHandle
from carwash_voice.voice.tools import ToolState

# --- prompts -----------------------------------------------------------------------------------


def test_inbound_prompt_has_persona_recording_notice_and_caller(settings: Settings) -> None:
    p = build_system_prompt(settings, "inbound", caller_number="+919845012345")
    assert "Asha" in p and "Sparkle Car Wash" in p
    assert "recorded" in p
    assert "Kannada" in p and "Hinglish" in p
    assert "+919845012345" in p
    assert "Never invent" in p


def test_inbound_prompt_without_caller_number(settings: Settings) -> None:
    assert "not known" in build_system_prompt(settings, "inbound")


def test_prompt_uses_configured_persona(settings: Settings) -> None:
    s = settings.model_copy(update={"business_name": "Shine Wash", "agent_name": "Meera"})
    p = build_system_prompt(s, "inbound")
    assert "Meera" in p and "Shine Wash" in p and "Sparkle" not in p


def test_outbound_prompt_has_job_details(settings: Settings) -> None:
    brief = OutboundBrief(7, "Ravi", "CW-12345", "Your refund has been approved")
    p = build_system_prompt(settings, "outbound", outbound=brief)
    assert "OUTBOUND" in p and "Ravi" in p and "CW-12345" in p
    assert "Your refund has been approved" in p
    assert "complete_outbound_job with job_id 7" in p


def test_outbound_prompt_needs_brief(settings: Settings) -> None:
    with pytest.raises(ValueError):
        build_system_prompt(settings, "outbound")


def test_greeting_trigger_differs_by_direction() -> None:
    assert greeting_trigger("inbound") != greeting_trigger("outbound")


# --- tools -------------------------------------------------------------------------------------


def _state(
    direction: str = "inbound", caller: str | None = "+919845012345", job: int | None = None
):
    call = CallContext("c1", direction, caller, job)
    return ToolState(call=call, handle=CallHandle())


def test_complaint_flow_uses_caller_number(session: Session) -> None:
    st = _state()
    up = tools.upsert_customer(session, st, {"name": "Ravi", "car_registration": "ka 01 ab 1234"})
    assert up["phone"] == "+919845012345"  # defaulted from the caller id
    t = tools.create_ticket(
        session,
        st,
        {"category": "quality", "description": "Dirty seats", "wash_location": "Indiranagar"},
    )
    assert t["ticket_ref"].startswith("CW-")
    assert t["say_it_as"].startswith("C W ")
    assert st.handle.ticket_id is not None  # stored on the call at the end
    status = tools.get_ticket_status(session, st, {"public_ref": t["ticket_ref"]})
    assert status["status"] == "open and waiting to be picked up"


def test_create_ticket_needs_customer(session: Session) -> None:
    out = tools.create_ticket(session, _state(), {"category": "quality", "description": "x"})
    assert "error" in out


def test_find_customer_and_status_by_phone(session: Session) -> None:
    st = _state()
    assert tools.find_customer(session, st, {}) == {"found": False}
    tools.upsert_customer(session, st, {"name": "Ravi"})
    tools.create_ticket(session, st, {"category": "billing", "description": "overcharged"})
    found = tools.find_customer(session, _state(), {})
    assert found["found"] and len(found["open_tickets"]) == 1
    by_phone = tools.get_ticket_status(session, _state(), {})
    assert len(by_phone["tickets"]) == 1
    assert tools.get_ticket_status(session, _state(caller=None), {})["error"]


def test_note_and_callback_tools(session: Session) -> None:
    st = _state()
    tools.upsert_customer(session, st, {"name": "Ravi"})
    ref = tools.create_ticket(session, st, {"category": "damage", "description": "scratch"})[
        "ticket_ref"
    ]
    assert tools.add_ticket_note(session, st, {"public_ref": ref, "note": "white Swift"})["ok"]
    out = tools.request_human_callback(
        session, st, {"public_ref": ref, "reason": "wants manager", "preferred_time": "evening"}
    )
    assert out["ok"]
    assert tickets.get_ticket(session, ref).status == TicketStatus.CALLBACK_REQUESTED


def test_complete_outbound_job_outcomes(session: Session) -> None:
    c = customers.upsert_customer(session, name="Ravi", phone="9845012345")
    t = tickets.create_ticket(session, c.id, "billing", "refund")
    job = outbound.create_job(session, "Refund approved", ticket_ref=t.public_ref)
    st = _state("outbound", job=job.id)
    assert tools.complete_outbound_job(session, st, {"outcome": "bogus"})["error"]
    assert tools.complete_outbound_job(session, st, {"outcome": "delivered", "note": "happy"})["ok"]
    assert outbound.get_job(session, job.id).status == JobStatus.COMPLETED
    assert tools.complete_outbound_job(session, st, {"outcome": "call_back_later", "note": "6pm"})
    assert outbound.get_job(session, job.id).status == JobStatus.QUEUED
    assert tools.complete_outbound_job(session, st, {"outcome": "declined"})["ok"]
    assert outbound.get_job(session, job.id).status == JobStatus.FAILED
    assert "error" in tools.complete_outbound_job(session, _state(), {"outcome": "delivered"})


def _ticket_for(session: Session, phone: str, reg: str) -> str:
    c = customers.upsert_customer(session, name="Ravi", phone=phone, car_registration=reg)
    return tickets.create_ticket(session, c.id, "damage", "scratch on door").public_ref


def test_stranger_needs_registration_to_hear_a_ticket(session: Session) -> None:
    ref = _ticket_for(session, "9845012345", "KA01AB1234")
    stranger = _state(caller="+919900011122")
    assert tools.get_ticket_status(session, stranger, {"public_ref": ref}) == {
        "error": tools.PRIVACY_ERROR
    }
    assert "error" in tools.add_ticket_note(session, stranger, {"public_ref": ref, "note": "x"})
    assert "error" in tools.request_human_callback(
        session, stranger, {"public_ref": ref, "reason": "x"}
    )
    wrong = {"public_ref": ref, "car_registration": "KA01ZZ9999"}
    assert "error" in tools.get_ticket_status(session, stranger, wrong)
    right = {"public_ref": ref, "car_registration": "ka 01 ab 1234"}
    assert tools.get_ticket_status(session, stranger, right)["ticket_ref"] == ref
    # once confirmed, the rest of the call can use the ticket
    assert tools.add_ticket_note(session, stranger, {"public_ref": ref, "note": "red car"})["ok"]


def test_stranger_cannot_list_another_numbers_tickets(session: Session) -> None:
    _ticket_for(session, "9845012345", "KA01AB1234")
    stranger = _state(caller="+919900011122")
    out = tools.get_ticket_status(session, stranger, {"phone": "9845012345"})
    assert out == {"error": tools.PRIVACY_ERROR}
    both = {"phone": "9845012345", "car_registration": "KA01AB1234"}
    assert len(tools.get_ticket_status(session, stranger, both)["tickets"]) == 1


def test_find_customer_by_registration_alone_reveals_nothing(session: Session) -> None:
    _ticket_for(session, "9845012345", "KA01AB1234")
    stranger = _state(caller="+919900011122")
    out = tools.find_customer(session, stranger, {"car_registration": "KA01AB1234"})
    assert out["found"] is False and "name" not in out and stranger.customer_id is None
    owner = tools.find_customer(session, _state(), {})
    assert owner["found"] and owner["name"] == "Ravi" and len(owner["open_tickets"]) == 1


def test_upsert_never_takes_over_another_customers_number(session: Session) -> None:
    owner = customers.upsert_customer(
        session, name="Ravi", phone="9845012345", car_registration="KA01AB1234"
    )
    stranger = _state(caller="+919900011122")
    out = tools.upsert_customer(
        session, stranger, {"name": "Someone", "car_registration": "KA01AB1234"}
    )
    assert out["customer_id"] != owner.id and out["phone"] == "+919900011122"
    session.refresh(owner)
    assert owner.phone == "+919845012345" and owner.name == "Ravi"


def test_saying_a_victims_number_does_not_unlock_their_record(session: Session) -> None:
    """Review finding 1a: a stranger names the victim's phone number in upsert_customer."""
    ref = _ticket_for(session, "9845012345", "KA01AB1234")
    victim = customers.find_customer(session, phone="9845012345")
    stranger = _state(caller="+919900011122")
    out = tools.upsert_customer(session, stranger, {"name": "Mallory", "phone": "9845012345"})
    assert out["customer_id"] != victim.id and out["phone"] == "+919900011122"
    session.refresh(victim)
    assert victim.name == "Ravi"
    assert tools.get_ticket_status(session, stranger, {"phone": "9845012345"}) == {
        "error": tools.PRIVACY_ERROR
    }
    assert tools.get_ticket_status(session, stranger, {"public_ref": ref}) == {
        "error": tools.PRIVACY_ERROR
    }


def test_unknown_caller_with_victims_registration_gets_a_new_record(session: Session) -> None:
    """Review finding 1b: no caller number (withheld) plus the victim's car registration."""
    _ticket_for(session, "9845012345", "KA01AB1234")
    victim = customers.find_customer(session, phone="9845012345")
    anon = _state(caller=None)
    out = tools.upsert_customer(
        session, anon, {"name": "Mallory", "car_registration": "KA01AB1234"}
    )
    assert out["customer_id"] != victim.id and out["phone"] is None
    session.refresh(victim)
    assert victim.name == "Ravi"
    found = tools.find_customer(session, anon, {"car_registration": "KA01AB1234"})
    assert "name" not in found or found["name"] != "Ravi"


def test_upsert_updates_the_callers_own_record(session: Session) -> None:
    st = _state()
    first = tools.upsert_customer(session, st, {"name": "Ravi"})
    # a later call from the same number updates the same record
    again = tools.upsert_customer(
        session, _state(), {"name": "Ravi K", "car_registration": "ka01ab1234"}
    )
    assert again["customer_id"] == first["customer_id"]
    c = customers.get_customer(session, first["customer_id"])
    assert c.name == "Ravi K" and c.car_registration == "KA01AB1234"


def test_create_ticket_ignores_an_unconfirmed_customer_id(session: Session) -> None:
    """Review finding 2: a model-supplied customer_id must not reach another customer."""
    _ticket_for(session, "9845012345", "KA01AB1234")
    victim = customers.find_customer(session, phone="9845012345")
    stranger = _state(caller="+919900011122")
    out = tools.create_ticket(
        session, stranger, {"customer_id": victim.id, "category": "other", "description": "x"}
    )
    assert "error" in out


def test_lookups_do_not_reveal_what_exists(session: Session) -> None:
    """Review finding 6: same reply for unknown and for not-confirmed."""
    ref = _ticket_for(session, "9845012345", "KA01AB1234")
    stranger = _state(caller="+919900011122")
    known = tools.get_ticket_status(session, stranger, {"public_ref": ref})
    unknown_ref = "CW-99999" if ref != "CW-99999" else "CW-99998"
    unknown = tools.get_ticket_status(session, stranger, {"public_ref": unknown_ref})
    assert known == unknown == {"error": tools.PRIVACY_ERROR}
    known_phone = tools.get_ticket_status(session, stranger, {"phone": "9845012345"})
    unknown_phone = tools.get_ticket_status(session, stranger, {"phone": "9845099999"})
    assert known_phone == unknown_phone == {"error": tools.PRIVACY_ERROR}
    assert tools.add_ticket_note(session, stranger, {"public_ref": unknown_ref, "note": "x"}) == {
        "error": tools.PRIVACY_ERROR
    }


def test_schemas_per_direction() -> None:
    inbound = {s.name for s in tools.tool_schemas("inbound").standard_tools}
    outbound_names = {s.name for s in tools.tool_schemas("outbound").standard_tools}
    expected = {
        "find_customer",
        "upsert_customer",
        "create_ticket",
        "get_ticket_status",
        "add_ticket_note",
        "request_human_callback",
        "end_call",
    }
    assert inbound == expected
    assert outbound_names == expected | {"complete_outbound_job"}


async def test_async_handlers_wrap_errors_and_arm_end_call(client: TestClient) -> None:
    armed: list[str] = []
    st = _state()
    handlers = tools.make_handlers(client.app.state.session_factory, st, armed.append)
    results: list[Any] = []

    async def cb(result: Any, **_: Any) -> None:
        results.append(result)

    def params(args: dict[str, Any]) -> Any:
        return SimpleNamespace(arguments=args, result_callback=cb)

    await handlers["get_ticket_status"](params({"public_ref": "CW-00000"}))
    assert results[-1] == {"error": tools.PRIVACY_ERROR}
    await handlers["upsert_customer"](params({"name": "Ravi"}))
    assert results[-1]["customer_id"]
    await handlers["end_call"](params({"reason": "done"}))
    assert armed == ["done"] and results[-1]["ok"]
    assert "already said goodbye" in results[-1]["instruction"]


# --- pipeline helpers --------------------------------------------------------------------------


async def test_greet_on_connect_asks_llm_to_run() -> None:
    down, _ = await run_test(
        GreetOnConnect(),
        frames_to_send=[ClientConnectedFrame()],
        expected_down_frames=[ClientConnectedFrame, LLMRunFrame],
    )
    assert len(down) == 2


class _FakeHandle(CallHandle):
    def __init__(self) -> None:
        super().__init__()
        self.ended: list[str] = []
        self.event = asyncio.Event()

    async def end(self, reason: str) -> None:
        self.ended.append(reason)
        self.event.set()


async def test_end_call_watcher_ignores_speech_when_not_armed() -> None:
    handle = _FakeHandle()
    await run_test(
        EndCallWatcher(handle, fallback_secs=30), frames_to_send=[BotStoppedSpeakingFrame()]
    )
    assert handle.ended == []


async def test_end_call_watcher_silent_agent_waits_for_goodbye_then_ends() -> None:
    handle = _FakeHandle()
    watcher = EndCallWatcher(handle, fallback_secs=30, silence_secs=30)
    watcher.arm("customer_done")  # armed while the agent is silent
    await run_test(
        watcher,
        frames_to_send=[
            BotStoppedSpeakingFrame(),  # stray stop with no speech after arming: ignored
            BotStartedSpeakingFrame(),  # the goodbye starts
            SleepFrame(),  # system frames overtake queued ones; keep the real-call order
            BotStoppedSpeakingFrame(),  # and finishes
        ],
    )
    assert handle.ended == ["customer_done"]


async def test_end_call_watcher_ends_when_goodbye_already_playing_stops() -> None:
    handle = _FakeHandle()
    watcher = EndCallWatcher(handle, fallback_secs=30, silence_secs=30)
    watcher._bot_speaking = True  # goodbye said in the same turn as the end_call tool call
    watcher.arm("customer_done")
    await run_test(watcher, frames_to_send=[BotStoppedSpeakingFrame()])
    assert handle.ended == ["customer_done"]  # no second goodbye needed


async def test_end_call_watcher_ends_quickly_if_agent_stays_silent() -> None:
    handle = _FakeHandle()
    watcher = EndCallWatcher(handle, fallback_secs=30, silence_secs=0.1)
    watcher.arm("stuck")
    await asyncio.wait_for(handle.event.wait(), timeout=2)
    assert handle.ended == ["stuck"]


# --- provider ----------------------------------------------------------------------------------


async def test_provider_requires_openai_settings(client: TestClient, settings: Settings) -> None:
    provider = OpenAIRealtimeProvider(settings, client.app.state.session_factory)
    with pytest.raises(ConfigError):
        await provider.build(CallContext("c1", "inbound"), CallHandle())


async def test_provider_builds_pipeline_parts(client: TestClient, settings: Settings) -> None:
    s = settings.model_copy(
        update={
            "openai_api_key": "sk-test-not-real",
            "openai_realtime_model": "gpt-realtime-2.1",
            "openai_realtime_voice": "marin",
        }
    )
    provider = OpenAIRealtimeProvider(s, client.app.state.session_factory)
    parts = await provider.build(CallContext("c1", "inbound", "+919845012345"), CallHandle())
    names = [type(p).__name__ for p in parts]
    assert names == [
        "GreetOnConnect",
        "LLMUserAggregator",
        "OpenAIRealtimeLLMService",
        "EndCallWatcher",
        "LLMAssistantAggregator",
    ]


def test_app_uses_real_provider_only_with_api_key(settings: Settings) -> None:
    from carwash_voice.main import create_app

    with TestClient(create_app(settings)) as c:
        assert c.app.state.provider is None
    keyed = settings.model_copy(update={"openai_api_key": "sk-test-not-real"})
    with TestClient(create_app(keyed)) as c:
        assert isinstance(c.app.state.provider, OpenAIRealtimeProvider)
