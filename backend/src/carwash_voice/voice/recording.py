"""Call recording: WAV encoding and a small storage interface.

Only a local-disk store exists today. Anything with save/open/delete (for example an
S3-compatible store) can replace it without touching the call session.
"""

from __future__ import annotations

import io
import re
import wave
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO, Protocol

_SAFE_ID = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")


def wav_bytes(pcm: bytes, sample_rate: int, num_channels: int) -> bytes:
    """Wrap raw 16-bit PCM in a WAV container."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(num_channels)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm)
    return buf.getvalue()


class RecordingStore(Protocol):
    def save(self, call_id: str, data: bytes) -> str:
        """Store the audio and return a path/key to keep on the call row."""
        ...

    def open(self, path: str) -> BinaryIO: ...

    def delete(self, path: str) -> bool:
        """Remove one recording; return False if it was already gone."""
        ...


class LocalRecordingStore:
    """Files under root/<yyyy>/<mm>/<call_id>.wav; the returned path is relative to root."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)

    def save(self, call_id: str, data: bytes, when: datetime | None = None) -> str:
        if not _SAFE_ID.match(call_id) or call_id in {".", ".."}:
            raise ValueError(f"unsafe call id for a file name: {call_id!r}")
        when = when or datetime.now(UTC)
        rel = f"{when:%Y}/{when:%m}/{call_id}.wav"
        target = self._root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return rel

    def resolve(self, path: str) -> Path:
        """Absolute file path for a stored recording; refuses anything outside the root."""
        root = self._root.resolve()
        full = (root / path).resolve()
        if not full.is_relative_to(root):
            raise ValueError("recording path escapes the recordings folder")
        return full

    def open(self, path: str) -> BinaryIO:
        return self.resolve(path).open("rb")

    def delete(self, path: str) -> bool:
        full = self.resolve(path)
        if not full.exists():
            return False
        full.unlink()
        return True
