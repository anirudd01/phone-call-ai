import asyncio
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pipecat.frames.frames import (
    BotStoppedSpeakingFrame,
    ClientConnectedFrame,
    LLMFullResponseStartFrame,
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
    assert "error" in results[-1] and "not found" in results[-1]["error"]
    await handlers["upsert_customer"](params({"name": "Ravi"}))
    assert results[-1]["customer_id"]
    await handlers["end_call"](params({"reason": "done"}))
    assert armed == ["done"] and results[-1]["ok"]


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


async def test_end_call_watcher_waits_for_goodbye_then_ends() -> None:
    handle = _FakeHandle()
    watcher = EndCallWatcher(handle, fallback_secs=30)
    watcher.arm("customer_done")
    await run_test(
        watcher,
        frames_to_send=[
            BotStoppedSpeakingFrame(),  # the sentence already being said: not the goodbye
            LLMFullResponseStartFrame(),  # the goodbye response starts
            SleepFrame(),  # system frames overtake queued ones; keep the real-call order
            BotStoppedSpeakingFrame(),  # and finishes speaking
        ],
    )
    assert handle.ended == ["customer_done"]


async def test_end_call_watcher_fallback_timeout() -> None:
    handle = _FakeHandle()
    watcher = EndCallWatcher(handle, fallback_secs=0.1)
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
