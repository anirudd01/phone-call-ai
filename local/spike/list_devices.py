"""List every audio device: index, host API, channels, default sample rate.

Run it before the call and again during the call; note which devices appear only
during the call. Devices that look like Bluetooth hands-free are marked with <<<.

    uv run python list_devices.py [--name "My Phone"]
"""

from __future__ import annotations

import argparse

import sounddevice as sd

from _common import HIGHLIGHT


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", help="Also highlight names containing this text (phone name)")
    args = parser.parse_args()

    marks = list(HIGHLIGHT)
    if args.name:
        marks.append(args.name.lower())

    hostapis = sd.query_hostapis()
    print(f"{'idx':>3}  {'host API':<22} {'in':>3} {'out':>3} {'rate':>6}  name")
    for i, d in enumerate(sd.query_devices()):
        api = hostapis[d["hostapi"]]["name"]
        flag = "  <<<" if any(m in d["name"].lower() for m in marks) else ""
        print(
            f"{i:>3}  {api:<22} {d['max_input_channels']:>3} {d['max_output_channels']:>3} "
            f"{d['default_samplerate']:>6.0f}  {d['name']}{flag}"
        )
    print("\nPrefer entries whose host API is 'Windows WASAPI'.")


if __name__ == "__main__":
    main()
