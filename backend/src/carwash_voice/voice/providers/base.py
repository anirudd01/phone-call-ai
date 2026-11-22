"""The AI-provider seam.

A provider turns "one call" into the Pipecat processors that sit between the transport's
input and output (speech-to-speech service, context aggregators, tools). Swapping OpenAI
Realtime for Gemini Live or an STT -> LLM -> TTS cascade means writing another provider.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from pipecat.processors.frame_processor import FrameProcessor

if TYPE_CHECKING:
    from carwash_voice.voice.session import CallContext, CallHandle


class VoiceProvider(Protocol):
    def build(self, call: CallContext, handle: CallHandle) -> list[FrameProcessor]:
        """Return the processors that go between transport.input() and transport.output()."""
        ...
