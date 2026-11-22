"""One call's lifecycle, independent of the phone transport.

A transport adapter (transports/local today, Exotel or Plivo later) creates a Pipecat
transport and a CallHandle, then calls run_call(). run_call creates the call record, builds
the pipeline with the provider, runs it until the call ends, and always finalises the record.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from loguru import logger
from pipecat.frames.frames import EndFrame, Frame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.transports.base_transport import BaseTransport
from pipecat.workers.runner import WorkerRunner
from sqlalchemy.orm import Session, sessionmaker

from carwash_voice.config import Settings
from carwash_voice.db.session import run_db
from carwash_voice.domain import calls
from carwash_voice.logging import call_logging
from carwash_voice.voice.providers.base import VoiceProvider

PIPELINE_IN_RATE = 16000  # what transports deliver to the pipeline
PIPELINE_OUT_RATE = 24000  # what OpenAI Realtime produces; transports resample to the wire rate


@dataclass
class CallContext:
    call_id: str
    direction: str  # "inbound" | "outbound"
    caller_number: str | None = None
    outbound_job_id: int | None = None
    source: str = "unknown"  # e.g. bridge id or CPaaS name, for logs


@dataclass
class CallResources:
    settings: Settings
    session_factory: sessionmaker[Session]
    provider: VoiceProvider


class CallHandle:
    """Lets tools, transports and timers end the call or report why it ended.

    The first reason given wins and becomes the call's end_reason.
    """

    def __init__(self, end_notice: Callable[[str], Frame] | None = None) -> None:
        # end_notice builds a transport-specific "agent finished" frame sent before the EndFrame.
        self._end_notice = end_notice
        self._worker: PipelineWorker | None = None
        self.end_reason: str | None = None
        self.ticket_id: int | None = None  # set by tools; stored on the call at the end

    def bind(self, worker: PipelineWorker) -> None:
        self._worker = worker

    def note_reason(self, reason: str) -> None:
        if self.end_reason is None:
            self.end_reason = reason

    async def end(self, reason: str) -> None:
        """End the call gracefully: queued audio is flushed, then the pipeline stops."""
        self.note_reason(reason)
        if self._worker is None:
            return
        if self._end_notice is not None:
            await self._worker.queue_frame(self._end_notice(reason))
        await self._worker.queue_frame(EndFrame())

    async def cancel(self, reason: str) -> None:
        """Stop immediately (peer already gone)."""
        self.note_reason(reason)
        if self._worker is not None:
            await self._worker.cancel(reason=reason)


async def run_call(
    call: CallContext,
    transport: BaseTransport,
    handle: CallHandle,
    res: CallResources,
    on_ready: Callable[[], Frame | None] | None = None,
) -> str:
    """Run one call to the end and return its end reason."""
    with call_logging(call.call_id):
        logger.info(
            "Call starting ({}, {}, from {})", call.direction, call.source, call.caller_number
        )
        await run_db(
            res.session_factory,
            calls.create_call,
            call.call_id,
            call.direction,
            call.caller_number,
            call.outbound_job_id,
        )
        timer: asyncio.Task[None] | None = None
        try:
            processors = await res.provider.build(call, handle)
            pipeline = Pipeline([transport.input(), *processors, transport.output()])
            worker = PipelineWorker(
                pipeline,
                params=PipelineParams(
                    audio_in_sample_rate=PIPELINE_IN_RATE, audio_out_sample_rate=PIPELINE_OUT_RATE
                ),
                enable_rtvi=False,
            )
            handle.bind(worker)

            @transport.event_handler("on_client_connected")
            async def _connected(_transport: Any, _ws: Any) -> None:
                if on_ready is not None:
                    frame = on_ready()
                    if frame is not None:
                        await worker.queue_frame(frame)

            @transport.event_handler("on_client_disconnected")
            async def _disconnected(_transport: Any, _ws: Any) -> None:
                logger.info("Peer disconnected")
                await handle.cancel("remote_hangup")

            async def _max_duration() -> None:
                await asyncio.sleep(res.settings.max_call_seconds)
                logger.warning("Call hit the {} s cap", res.settings.max_call_seconds)
                await handle.end("max_duration")

            timer = asyncio.create_task(_max_duration())
            runner = WorkerRunner(handle_sigint=False)
            await runner.add_workers(worker)
            await runner.run()
            handle.note_reason("completed")
        except asyncio.CancelledError:
            handle.note_reason("cancelled")
            raise
        except Exception:
            logger.exception("Call failed")
            handle.note_reason("error")
        finally:
            if timer is not None:
                timer.cancel()
            reason = handle.end_reason or "unknown"
            await asyncio.shield(
                run_db(
                    res.session_factory,
                    calls.finalize_call,
                    call.call_id,
                    reason,
                    ticket_id=handle.ticket_id,
                )
            )
            logger.info("Call finished: {}", reason)
        return reason
