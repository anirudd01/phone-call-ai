"""Play a WAV (or a generated test tone sequence) into an output device during a call.

    uv run python play_into_call.py --device "Hands-Free" --wav prompt.wav
    uv run python play_into_call.py --device "Hands-Free"        # no --wav: plays tones

The tone sequence is three beeps rising in pitch (440, 660, 880 Hz), each half a second.
The caller on the other phone should hear them.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import sounddevice as sd

from _common import device_rate, find_device, read_wav, resample


def tones(rate: int) -> np.ndarray:
    parts = []
    for freq in (440, 660, 880):
        t = np.arange(int(0.5 * rate)) / rate
        parts.append(0.4 * np.sin(2 * np.pi * freq * t))
        parts.append(np.zeros(int(0.2 * rate)))
    return (np.concatenate(parts) * 32767).astype(np.int16)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", required=True, help="Substring of the output device name")
    parser.add_argument("--wav", type=Path, help="16-bit PCM WAV to play; default is tones")
    args = parser.parse_args()

    index = find_device(args.device, "output")
    rate = device_rate(index)
    if args.wav:
        data, src_rate = read_wav(args.wav)
        data = resample(data, src_rate, rate)
    else:
        data = tones(rate)
    print(f"Playing {len(data) / rate:.1f} s into the call at {rate} Hz...")
    sd.play(data, samplerate=rate, device=index)
    sd.wait()
    print("Done. Did the caller hear it clearly?")


if __name__ == "__main__":
    main()
