"""Record 5 s from the call, then play it back into the call (caller hears themselves).

    uv run python loopback_test.py --in-device "Hands-Free" --out-device "Hands-Free"

Ask the caller to say a sentence when it says "Speak now". Then they should hear it back.
The recording is also saved to loopback.wav.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import sounddevice as sd

from _common import device_rate, find_device, level_report, resample, write_wav


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in-device", required=True)
    parser.add_argument("--out-device", required=True)
    parser.add_argument("--seconds", type=float, default=5.0)
    parser.add_argument("--save", type=Path, default=Path("loopback.wav"))
    args = parser.parse_args()

    in_idx = find_device(args.in_device, "input")
    out_idx = find_device(args.out_device, "output")
    in_rate = device_rate(in_idx)
    out_rate = device_rate(out_idx)

    print(f"Speak now ({args.seconds:.0f} s)...")
    rec = sd.rec(
        int(args.seconds * in_rate), samplerate=in_rate, channels=1, dtype="int16", device=in_idx
    )
    sd.wait()
    mono = np.asarray(rec).reshape(-1)
    write_wav(args.save, mono, in_rate)
    print(f"Recorded. Levels: {level_report(mono)}")

    print("Playing back into the call...")
    sd.play(resample(mono, in_rate, out_rate), samplerate=out_rate, device=out_idx)
    sd.wait()
    print("Done. Did the caller hear themselves? Note any echo or delay.")


if __name__ == "__main__":
    main()
