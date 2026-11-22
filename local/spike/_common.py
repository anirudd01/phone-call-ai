"""Shared helpers for the Task 0 spike scripts (device lookup, WAV reading/writing)."""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
import sounddevice as sd

HIGHLIGHT = ("hands-free", "hands free", "ag audio", "handsfree")


def find_device(substr: str, kind: str) -> int:
    """Return the index of the best device whose name contains `substr`.

    `kind` is "input" or "output". WASAPI devices are preferred when several host APIs
    expose the same device.
    """
    key = "max_input_channels" if kind == "input" else "max_output_channels"
    hostapis = sd.query_hostapis()
    matches = [
        (i, d)
        for i, d in enumerate(sd.query_devices())
        if substr.lower() in d["name"].lower() and d[key] > 0
    ]
    if not matches:
        raise SystemExit(f"No {kind} device with '{substr}' in its name. Run list_devices.py.")

    def rank(item: tuple[int, dict]) -> int:
        return 0 if "WASAPI" in hostapis[item[1]["hostapi"]]["name"] else 1

    matches.sort(key=rank)
    index, dev = matches[0]
    print(
        f"Using {kind} device #{index}: {dev['name']} "
        f"[{hostapis[dev['hostapi']]['name']}] default rate {dev['default_samplerate']:.0f} Hz"
    )
    return index


def device_rate(index: int) -> int:
    return int(sd.query_devices(index)["default_samplerate"])


def write_wav(path: Path, data: np.ndarray, rate: int) -> None:
    """Write mono int16 audio."""
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(data.astype(np.int16).tobytes())


def read_wav(path: Path) -> tuple[np.ndarray, int]:
    """Read a 16-bit WAV, mixed down to mono int16."""
    with wave.open(str(path), "rb") as w:
        if w.getsampwidth() != 2:
            raise SystemExit("Only 16-bit PCM WAV files are supported.")
        rate = w.getframerate()
        channels = w.getnchannels()
        raw = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    if channels > 1:
        raw = raw.reshape(-1, channels).mean(axis=1).astype(np.int16)
    return raw, rate


def resample(data: np.ndarray, src: int, dst: int) -> np.ndarray:
    """Plain linear resampling; good enough for a feasibility test."""
    if src == dst or len(data) == 0:
        return data
    n_out = int(len(data) * dst / src)
    x_old = np.linspace(0.0, 1.0, num=len(data), endpoint=False)
    x_new = np.linspace(0.0, 1.0, num=n_out, endpoint=False)
    return np.interp(x_new, x_old, data.astype(np.float32)).astype(np.int16)


def level_report(data: np.ndarray) -> str:
    """Peak and RMS in dBFS, so the user can tell silence from real audio."""
    if len(data) == 0:
        return "no samples"
    f = data.astype(np.float32) / 32768.0
    peak = float(np.max(np.abs(f)))
    rms = float(np.sqrt(np.mean(f**2)))

    def db(x: float) -> str:
        return "-inf" if x <= 0 else f"{20 * np.log10(x):.1f}"

    return f"peak {db(peak)} dBFS, rms {db(rms)} dBFS"
