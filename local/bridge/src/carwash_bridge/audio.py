"""Audio plumbing that needs no sound hardware: framing, resampling, playback buffer."""

from __future__ import annotations

import threading

import numpy as np
import soxr

WIRE_RATE = 16000
FRAME_MS = 20
FRAME_BYTES = WIRE_RATE * FRAME_MS // 1000 * 2  # 640 bytes of 16-bit mono


class Framer:
    """Collects PCM bytes and hands back whole 20 ms frames."""

    def __init__(self, frame_bytes: int = FRAME_BYTES) -> None:
        self._size = frame_bytes
        self._buf = bytearray()

    def push(self, data: bytes) -> list[bytes]:
        self._buf.extend(data)
        frames = []
        while len(self._buf) >= self._size:
            frames.append(bytes(self._buf[: self._size]))
            del self._buf[: self._size]
        return frames


class PcmResampler:
    """Streaming 16-bit mono resampler between two rates (bytes in, bytes out)."""

    def __init__(self, in_rate: int, out_rate: int) -> None:
        self._same = in_rate == out_rate
        self._stream = None if self._same else soxr.ResampleStream(in_rate, out_rate, 1, "int16")

    def process(self, data: bytes) -> bytes:
        if self._same or not data:
            return data
        out = self._stream.resample_chunk(np.frombuffer(data, dtype=np.int16))
        return out.tobytes()


class JitterBuffer:
    """Playback buffer: waits for a small head start, then plays smoothly; clear() drops it.

    Thread-safe because the sound card callback and the network task both touch it.
    """

    def __init__(self, prebuffer_bytes: int) -> None:
        self._prebuffer = prebuffer_bytes
        self._buf = bytearray()
        self._playing = False
        self._lock = threading.Lock()

    def write(self, data: bytes) -> None:
        with self._lock:
            self._buf.extend(data)

    def clear(self) -> None:
        with self._lock:
            self._buf.clear()
            self._playing = False

    def read(self, n: int) -> bytes:
        """Return exactly n bytes, padding with silence when the buffer runs dry."""
        with self._lock:
            if not self._playing and len(self._buf) >= self._prebuffer:
                self._playing = True
            if not self._playing:
                return bytes(n)
            chunk = bytes(self._buf[:n])
            del self._buf[:n]
            if len(chunk) < n:
                self._playing = False  # underrun: rebuild the head start
                chunk += bytes(n - len(chunk))
            return chunk

    def __len__(self) -> int:
        with self._lock:
            return len(self._buf)
