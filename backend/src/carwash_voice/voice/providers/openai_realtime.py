"""OpenAI Realtime (speech-to-speech) provider built on Pipecat's OpenAIRealtimeLLMService."""

from __future__ import annotations

from loguru import logger
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair
from pipecat.processors.frame_processor import FrameProcessor
from pipecat.services.openai.realtime import events
from pipecat.services.openai.realtime.llm import OpenAIRealtimeLLMService
from sqlalchemy.orm import Session, sessionmaker

from carwash_voice.config import Settings
from carwash_voice.db.models import Ticket
from carwash_voice.db.session import run_db
from carwash_voice.domain import customers, outbound
from carwash_voice.voice.processors import EndCallWatcher, GreetOnConnect
from carwash_voice.voice.prompts import OutboundBrief, build_system_prompt, greeting_trigger
from carwash_voice.voice.session import CallContext, CallHandle
from carwash_voice.voice.tools import ToolState, make_handlers, tool_schemas


def _load_outbound_brief(session: Session, job_id: int) -> OutboundBrief:
    job = outbound.get_job(session, job_id)
    customer = customers.get_customer(session, job.customer_id)
    ticket = session.get(Ticket, job.ticket_id) if job.ticket_id else None
    ref = ticket.public_ref if ticket else None
    return OutboundBrief(
        job_id=job.id, customer_name=customer.name, ticket_ref=ref, message=job.message
    )


class OpenAIRealtimeProvider:
    def __init__(self, settings: Settings, session_factory: sessionmaker[Session]) -> None:
        self._settings = settings
        self._session_factory = session_factory

    async def build(self, call: CallContext, handle: CallHandle) -> list[FrameProcessor]:
        s = self._settings
        s.require_openai()  # only needed once a call actually starts
        brief: OutboundBrief | None = None
        if call.direction == "outbound" and call.outbound_job_id is not None:
            brief = await run_db(self._session_factory, _load_outbound_brief, call.outbound_job_id)

        prompt = build_system_prompt(s, call.direction, call.caller_number, brief)
        session_properties = events.SessionProperties(
            audio=events.AudioConfiguration(
                input=events.AudioInput(
                    transcription=events.InputAudioTranscription(),
                    turn_detection=events.TurnDetection(),  # server-side VAD, interruptions on
                ),
                output=events.AudioOutput(voice=s.openai_realtime_voice or None),
            ),
        )
        llm = OpenAIRealtimeLLMService(
            api_key=s.openai_api_key,
            settings=OpenAIRealtimeLLMService.Settings(
                model=s.openai_realtime_model,
                system_instruction=prompt,
                session_properties=session_properties,
            ),
        )

        watcher = EndCallWatcher(handle)
        state = ToolState(call=call, handle=handle)
        for name, fn in make_handlers(self._session_factory, state, watcher.arm).items():
            llm.register_function(name, fn)

        context = LLMContext(
            messages=[{"role": "user", "content": greeting_trigger(call.direction)}],
            tools=tool_schemas(call.direction),
        )
        aggregators = LLMContextAggregatorPair(context)
        logger.info("Realtime provider ready (model {})", s.openai_realtime_model)
        return [GreetOnConnect(), aggregators.user(), llm, watcher, aggregators.assistant()]
