"""Pipecat serializer for the local bridge's wire format (LOCAL TESTING ONLY)."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from loguru import logger
from pipecat.frames.frames import (
    AudioRawFrame,
    Frame,
    InputAudioRawFrame,
    InterruptionFrame,
    OutputTransportMessageFrame,
    OutputTransportMessageUrgentFrame,
)
from pipecat.serializers.base_serializer import FrameSerializer

from carwash_voice.transports.local import protocol


class LocalBridgeFrameSerializer(FrameSerializer):
    """Binary frames are PCM16 mono 16 kHz audio; text frames are JSON control messages.

    Incoming audio becomes InputAudioRawFrame, an interruption becomes {"type": "clear"} and
    transport message frames are sent as JSON. Incoming `stop`/`mark` messages are reported to
    `on_control` (the session ends the call), not turned into frames.
    """

    class InputParams(FrameSerializer.InputParams):
        audio_in_sample_rate: int = protocol.SAMPLE_RATE
        audio_out_sample_rate: int = protocol.SAMPLE_RATE

    def __init__(self, on_control: Callable[[dict[str, Any]], None] | None = None) -> None:
        super().__init__(LocalBridgeFrameSerializer.InputParams())
        self._on_control = on_control

    async def serialize(self, frame: Frame) -> str | bytes | None:
        if isinstance(frame, InterruptionFrame):
            await self._reset_audio_out()
            return json.dumps(protocol.clear())
        if isinstance(frame, AudioRawFrame):
            data = await self._resample_audio_out(frame)
            return data or None
        if isinstance(frame, OutputTransportMessageFrame | OutputTransportMessageUrgentFrame):
            if self.should_ignore_frame(frame):
                return None
            return json.dumps(frame.message)
        return None

    async def deserialize(self, data: str | bytes) -> Frame | None:
        if isinstance(data, bytes):
            audio = await self._resample_audio_in(data)
            if not audio:
                return None
            return InputAudioRawFrame(audio=audio, num_channels=1, sample_rate=self._sample_rate)
        message = protocol.parse_control(data)
        if message is None:
            logger.warning("Ignoring non-JSON text frame from bridge")
            return None
        if self._on_control is not None:
            self._on_control(message)
        return None
