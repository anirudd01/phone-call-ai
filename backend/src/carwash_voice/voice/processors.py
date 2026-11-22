"""Small pipeline processors used by the voice providers."""

from __future__ import annotations

import asyncio

from loguru import logger
from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    ClientConnectedFrame,
    Frame,
    LLMRunFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from carwash_voice.voice.session import CallHandle


class GreetOnConnect(FrameProcessor):
    """Makes the agent speak first: when the transport reports the peer is connected, ask the
    LLM to run on the context's opening message."""

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        await self.push_frame(frame, direction)
        if isinstance(frame, ClientConnectedFrame):
            await self.push_frame(LLMRunFrame())


class EndCallWatcher(FrameProcessor):
    """Ends the call once the agent's goodbye has been spoken.

    Place it between the LLM and the transport output, so it sees the "bot started/stopped
    speaking" frames coming up from the output. The prompt asks the agent to say goodbye and
    call end_call in the same turn, so when end_call arms this watcher the goodbye is usually
    still playing: the call ends when that speech stops. If the agent is silent when armed, it
    waits up to `silence_secs` for a goodbye to start, then ends when it stops. `fallback_secs`
    caps how long a goodbye may take.
    """

    def __init__(
        self, handle: CallHandle, fallback_secs: float = 20.0, silence_secs: float = 5.0
    ) -> None:
        super().__init__()
        self._handle = handle
        self._fallback_secs = fallback_secs
        self._silence_secs = silence_secs
        self._armed_reason: str | None = None
        self._bot_speaking = False
        self._end_on_next_stop = False
        self._fallback: asyncio.Task[None] | None = None

    def arm(self, reason: str) -> None:
        if self._armed_reason is not None:
            return
        self._armed_reason = reason
        self._end_on_next_stop = self._bot_speaking
        logger.info("end_call requested: {} (agent speaking: {})", reason, self._bot_speaking)
        self._start_fallback(self._fallback_secs if self._bot_speaking else self._silence_secs)

    def _start_fallback(self, secs: float) -> None:
        if self._fallback is not None:
            self._fallback.cancel()
        self._fallback = asyncio.get_running_loop().create_task(self._end_after_timeout(secs))

    async def _end_after_timeout(self, secs: float) -> None:
        await asyncio.sleep(secs)
        logger.warning("No finished goodbye after {} s; ending the call", secs)
        await self._finish()

    async def _finish(self) -> None:
        reason, self._armed_reason = self._armed_reason, None
        if reason is not None:
            await self._handle.end(reason)

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        await self.push_frame(frame, direction)
        if isinstance(frame, BotStartedSpeakingFrame):
            self._bot_speaking = True
            if self._armed_reason is not None and not self._end_on_next_stop:
                self._end_on_next_stop = True  # the goodbye has started
                self._start_fallback(self._fallback_secs)
        elif isinstance(frame, BotStoppedSpeakingFrame):
            self._bot_speaking = False
            if self._armed_reason is not None and self._end_on_next_stop:
                if self._fallback is not None:
                    self._fallback.cancel()
                await self._finish()

    async def cleanup(self) -> None:
        await super().cleanup()
        if self._fallback is not None:
            self._fallback.cancel()
