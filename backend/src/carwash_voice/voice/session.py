"""One call's lifecycle, independent of the phone transport.

A transport adapter (transports/local today, Exotel or Plivo later) creates a Pipecat
transport and a CallHandle, then calls run_call(). run_call creates the call record, builds
the pipeline with the provider, runs it until the call ends, and always finalises the record.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from loguru import logger
from pipecat.frames.frames import EndFrame, Frame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.audio.audio_buffer_processor import AudioBufferProcessor
from pipecat.transports.base_transport import BaseTransport
from pipecat.workers.runner import WorkerRunner
from sqlalchemy.orm import Session, sessionmaker

from carwash_voice.config import Settings
from carwash_voice.db.session import run_db
from carwash_voice.domain import calls
from carwash_voice.logging import call_logging
from carwash_voice.voice.providers.base import VoiceProvider
from carwash_voice.voice.recording import LocalRecordingStore, RecordingStore, wav_bytes

PIPELINE_IN_RATE = 16000  # what transports deliver to the pipeline
PIPELINE_OUT_RATE = 24000  # what OpenAI Realtime produces; transports resample to the wire rate
RECORDING_RATE = 16000  # stereo WAV: caller on the left, agent on the right


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
    store: RecordingStore | None = None  # default: local files under settings.recordings_dir


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
        self.transcript: list[dict[str, Any]] = []

    def add_transcript(self, role: str, text: str, timestamp: str | None = None) -> None:
        """Record one spoken turn ("caller" or "agent"). Empty text is ignored."""
        text = (text or "").strip()
        if text:
            self.transcript.append(
                {"role": role, "text": text, "at": timestamp or datetime.now(UTC).isoformat()}
            )

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
        audio: dict[str, Any] = {}
        recorder = AudioBufferProcessor(
            sample_rate=RECORDING_RATE, num_channels=2, auto_start_recording=True
        )

        @recorder.event_handler("on_audio_data")
        async def _audio(_proc: Any, pcm: bytes, rate: int, channels: int) -> None:
            audio.update(pcm=pcm, rate=rate, channels=channels)

        try:
            processors = await res.provider.build(call, handle)
            # The recorder sits after the output so it hears both the caller and the agent.
            pipeline = Pipeline([transport.input(), *processors, transport.output(), recorder])
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
            try:
                # After a hang-up the cancel may not reach the recorder; flush what it holds.
                await recorder.stop_recording()
                # Pipecat runs event handlers as tasks; give ours a moment to store the audio.
                for _ in range(10):
                    if audio:
                        break
                    await asyncio.sleep(0.01)
            except (Exception, asyncio.CancelledError):
                # Best effort: finalising the call record below must still happen.
                logger.exception("Could not flush the recording buffer")
            audio_path = _save_recording(res, call.call_id, audio)
            await asyncio.shield(
                run_db(
                    res.session_factory,
                    calls.finalize_call,
                    call.call_id,
                    reason,
                    transcript=handle.transcript,
                    audio_path=audio_path,
                    ticket_id=handle.ticket_id,
                )
            )
            logger.info("Call finished: {}", reason)
        return reason


def _save_recording(res: CallResources, call_id: str, audio: dict[str, Any]) -> str | None:
    """Write the call's WAV; a storage problem is logged and never breaks the call record."""
    if not audio.get("pcm"):
        return None
    try:
        store = res.store or LocalRecordingStore(res.settings.recordings_dir)
        data = wav_bytes(audio["pcm"], audio["rate"], audio["channels"])
        path = store.save(call_id, data)
        logger.info("Recording saved: {} ({} bytes)", path, len(data))
        return path
    except Exception:
        logger.exception("Could not save the recording")
        return None
