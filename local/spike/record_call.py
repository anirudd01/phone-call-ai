"""Record from an input device during a call (what the remote caller says).

    uv run python record_call.py --device "Hands-Free" --seconds 15 --out caller.wav

Play caller.wav afterwards: you should hear the person on the other phone.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import sounddevice as sd

from _common import device_rate, find_device, level_report, write_wav


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", required=True, help="Substring of the input device name")
    parser.add_argument("--seconds", type=float, default=15.0)
    parser.add_argument("--out", type=Path, default=Path("caller.wav"))
    args = parser.parse_args()

    index = find_device(args.device, "input")
    rate = device_rate(index)
    print(f"Recording {args.seconds:.0f} s at {rate} Hz. Ask the caller to speak now...")
    data = sd.rec(
        int(args.seconds * rate), samplerate=rate, channels=1, dtype="int16", device=index
    )
    sd.wait()
    mono = np.asarray(data).reshape(-1)
    write_wav(args.out, mono, rate)
    print(f"Saved {args.out} ({rate} Hz). Levels: {level_report(mono)}")
    print("If the peak is -inf or below about -60 dBFS, no call audio is reaching this device.")


if __name__ == "__main__":
    main()
