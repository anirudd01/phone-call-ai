"""carwash-bridge command line: `devices` and `run`."""

from __future__ import annotations

import argparse
import asyncio
import contextlib

from carwash_bridge.app import Console, show_devices
from carwash_bridge.config import BridgeSettings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="carwash-bridge")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("devices", help="list audio devices")
    sub.add_parser("run", help="operator console")
    args = parser.parse_args(argv)
    if args.command == "devices":
        show_devices()
        return 0
    settings = BridgeSettings.from_env()
    settings.check()
    with contextlib.suppress(KeyboardInterrupt, EOFError):
        asyncio.run(Console(settings).run())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
