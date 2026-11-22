"""Fake AI provider for tests: echoes caller audio back, optionally ends the call."""

from __future__ import annotations

from pipecat.frames.frames import Frame, InputAudioRawFrame, OutputAudioRawFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from carwash_voice.voice.session import CallContext, CallHandle


class EchoProcessor(FrameProcessor):
    def __init__(self, handle: CallHandle, end_after_frames: int | None, end_reason: str) -> None:
        super().__init__()
        self._handle = handle
        self._end_after = end_after_frames
        self._end_reason = end_reason
        self._seen = 0

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        if isinstance(frame, InputAudioRawFrame):
            await self.push_frame(
                OutputAudioRawFrame(
                    audio=frame.audio, sample_rate=frame.sample_rate, num_channels=1
                )
            )
            self._seen += 1
            if self._end_after is not None and self._seen == self._end_after:
                await self._handle.end(self._end_reason)
            return
        await self.push_frame(frame, direction)


class EchoProvider:
    def __init__(self, end_after_frames: int | None = None, end_reason: str = "agent_done") -> None:
        self._end_after = end_after_frames
        self._end_reason = end_reason

    def build(self, call: CallContext, handle: CallHandle) -> list[FrameProcessor]:
        return [EchoProcessor(handle, self._end_after, self._end_reason)]
