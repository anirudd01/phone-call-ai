"""Sound-card access with sounddevice. Needs real hardware, so it is not unit tested."""

from __future__ import annotations

import asyncio
import re

import sounddevice as sd

from carwash_bridge.audio import (
    FRAME_BYTES,
    FRAME_MS,
    WIRE_RATE,
    Framer,
    JitterBuffer,
    PcmResampler,
)

PREBUFFER_MS = 80


def clean_name(name: str) -> str:
    """Windows gives multi-line, noisy Bluetooth names; make them one readable line."""
    m = re.match(r"(\w+) \(@[^;]*;%1 (.*?)%0\s*;\((.*)\)\)$", name, flags=re.S)
    if m:
        return f"{m.group(1)}: {m.group(2).strip()} ({m.group(3).strip()})"
    return " ".join(name.split())


def list_devices() -> list[str]:
    hostapis = sd.query_hostapis()
    lines = []
    for i, d in enumerate(sd.query_devices()):
        kinds = []
        if d["max_input_channels"] > 0:
            kinds.append("in")
        if d["max_output_channels"] > 0:
            kinds.append("out")
        api = hostapis[d["hostapi"]]["name"]
        lines.append(f"#{i:<3} [{'/'.join(kinds):<6}] {clean_name(d['name'])} ({api})")
    return lines


def find_device(substr: str, kind: str) -> int:
    key = "max_input_channels" if kind == "input" else "max_output_channels"
    hostapis = sd.query_hostapis()
    matches = [
        (i, d)
        for i, d in enumerate(sd.query_devices())
        if substr.lower() in clean_name(d["name"]).lower() and d[key] > 0
    ]
    if not matches:
        raise SystemExit(
            f"No {kind} device with '{substr}' in its name. Run: carwash-bridge devices"
        )
    matches.sort(key=lambda m: 0 if "WASAPI" in hostapis[m[1]["hostapi"]]["name"] else 1)
    return matches[0][0]


class LiveAudio:
    """Microphone to 20 ms 16 kHz frames, and 16 kHz audio to the speakers."""

    def __init__(self, in_device: str = "", out_device: str = "") -> None:
        self._in_index = find_device(in_device, "input") if in_device else None
        self._out_index = find_device(out_device, "output") if out_device else None
        self._in_rate = int(sd.query_devices(self._in_index, "input")["default_samplerate"])
        self._out_rate = int(sd.query_devices(self._out_index, "output")["default_samplerate"])
        self._mic_resampler = PcmResampler(self._in_rate, WIRE_RATE)
        self._spk_resampler = PcmResampler(WIRE_RATE, self._out_rate)
        self._framer = Framer()
        prebuffer = self._out_rate * 2 * PREBUFFER_MS // 1000
        self._jitter = JitterBuffer(prebuffer)
        self.frames: asyncio.Queue[bytes] = asyncio.Queue(maxsize=200)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._in: sd.RawInputStream | None = None
        self._out: sd.RawOutputStream | None = None

    def describe(self) -> str:
        mic = "default" if self._in_index is None else f"#{self._in_index}"
        spk = "default" if self._out_index is None else f"#{self._out_index}"
        return f"mic {mic} at {self._in_rate} Hz, speaker {spk} at {self._out_rate} Hz"

    def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._in = sd.RawInputStream(
            samplerate=self._in_rate,
            channels=1,
            dtype="int16",
            blocksize=self._in_rate * FRAME_MS // 1000,
            device=self._in_index,
            callback=self._mic_callback,
        )
        self._out = sd.RawOutputStream(
            samplerate=self._out_rate,
            channels=1,
            dtype="int16",
            blocksize=self._out_rate * FRAME_MS // 1000,
            device=self._out_index,
            callback=self._speaker_callback,
        )
        self._in.start()
        self._out.start()

    def stop(self) -> None:
        for stream in (self._in, self._out):
            if stream is not None:
                stream.stop()
                stream.close()
        self._in = self._out = None

    def play(self, pcm16k: bytes) -> None:
        self._jitter.write(self._spk_resampler.process(pcm16k))

    def clear(self) -> None:
        self._jitter.clear()

    def _mic_callback(self, indata, _frames, _time, _status) -> None:  # sounddevice thread
        for frame in self._framer.push(self._mic_resampler.process(bytes(indata))):
            assert len(frame) == FRAME_BYTES
            if self._loop is not None:
                self._loop.call_soon_threadsafe(self._offer, frame)

    def _offer(self, frame: bytes) -> None:
        if not self.frames.full():
            self.frames.put_nowait(frame)

    def _speaker_callback(self, outdata, frames, _time, _status) -> None:  # sounddevice thread
        outdata[:] = self._jitter.read(frames * 2)
