"""Small pipeline processors used by the voice providers."""

from __future__ import annotations

import asyncio

from loguru import logger
from pipecat.frames.frames import (
    BotStoppedSpeakingFrame,
    ClientConnectedFrame,
    Frame,
    LLMFullResponseStartFrame,
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
    """Ends the call after the agent's goodbye has been spoken.

    Place it between the LLM and the transport output, so it sees LLM frames going down and
    the "bot stopped speaking" frames coming up. Flow: the end_call tool calls arm(); the model
    then answers with a goodbye (a new LLM response); when the transport reports that speech
    finished, the call ends. A timeout ends it anyway if the goodbye never comes.
    """

    def __init__(self, handle: CallHandle, fallback_secs: float = 20.0) -> None:
        super().__init__()
        self._handle = handle
        self._fallback_secs = fallback_secs
        self._armed_reason: str | None = None
        self._goodbye_started = False
        self._fallback: asyncio.Task[None] | None = None

    def arm(self, reason: str) -> None:
        if self._armed_reason is not None:
            return
        self._armed_reason = reason
        logger.info("end_call requested: {}", reason)
        self._fallback = asyncio.get_running_loop().create_task(self._end_after_timeout())

    async def _end_after_timeout(self) -> None:
        await asyncio.sleep(self._fallback_secs)
        logger.warning("Goodbye did not finish in {} s; ending the call", self._fallback_secs)
        await self._finish()

    async def _finish(self) -> None:
        reason, self._armed_reason = self._armed_reason, None
        if reason is not None:
            await self._handle.end(reason)

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        await self.push_frame(frame, direction)
        if self._armed_reason is None:
            return
        if isinstance(frame, LLMFullResponseStartFrame):
            self._goodbye_started = True
        elif isinstance(frame, BotStoppedSpeakingFrame) and self._goodbye_started:
            if self._fallback is not None:
                self._fallback.cancel()
            await self._finish()

    async def cleanup(self) -> None:
        await super().cleanup()
        if self._fallback is not None:
            self._fallback.cancel()
