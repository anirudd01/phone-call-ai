"""Bridge settings from environment variables, with a simple .env file in the current folder."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_dotenv(path: Path = Path(".env")) -> None:
    """Read KEY=VALUE lines into os.environ without overriding values already set."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class BridgeSettings:
    ws_url: str
    http_url: str
    token: str
    bridge_id: str
    audio_mode: str  # "laptop" (default mic and speakers) or "bluetooth" (named devices)
    in_device: str
    out_device: str

    @classmethod
    def from_env(cls) -> BridgeSettings:
        load_dotenv()
        env = os.environ.get
        return cls(
            ws_url=env("BACKEND_WS_URL", "ws://localhost:8000/ws/local-bridge"),
            http_url=env("BACKEND_HTTP_URL", "http://localhost:8000"),
            token=env("BRIDGE_TOKEN", ""),
            bridge_id=env("BRIDGE_ID", "laptop"),
            audio_mode=env("AUDIO_MODE", "laptop").lower(),
            in_device=env("IN_DEVICE", ""),
            out_device=env("OUT_DEVICE", ""),
        )

    def check(self) -> None:
        if not self.token:
            raise SystemExit("BRIDGE_TOKEN is not set (put it in .env or the environment).")
        if self.audio_mode not in {"laptop", "bluetooth"}:
            raise SystemExit("AUDIO_MODE must be 'laptop' or 'bluetooth'.")
        if self.audio_mode == "bluetooth" and not (self.in_device and self.out_device):
            raise SystemExit("Bluetooth mode needs IN_DEVICE and OUT_DEVICE (run: devices).")
