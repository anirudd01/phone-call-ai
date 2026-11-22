"""Wire protocol v1 between the local bridge and the backend (see local/docs/bridge-protocol.md).

LOCAL TESTING ONLY: nothing outside transports/local may import this module.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ValidationError

PROTOCOL_VERSION = 1
SAMPLE_RATE = 16000
CLOSE_UNAUTHORIZED = 4401
CLOSE_BAD_START = 4400
CLOSE_UNAVAILABLE = 4503
START_TIMEOUT_SECS = 5.0


class StartMessage(BaseModel):
    type: Literal["start"]
    protocol: int
    call_id: str
    direction: Literal["inbound", "outbound"]
    caller_number: str | None = None
    outbound_job_id: int | None = None
    bridge_id: str = "unknown"


class StopMessage(BaseModel):
    type: Literal["stop"]
    reason: Literal["operator_hangup", "remote_hangup", "error"] = "operator_hangup"


def parse_start(text: str) -> StartMessage:
    """Parse the first message; raises ValueError with a short reason if it is not valid."""
    try:
        msg = StartMessage.model_validate_json(text)
    except ValidationError as exc:
        raise ValueError("first message must be a valid 'start' message") from exc
    if msg.protocol != PROTOCOL_VERSION:
        raise ValueError(f"unsupported protocol {msg.protocol}; expected {PROTOCOL_VERSION}")
    return msg


def parse_control(text: str) -> dict[str, Any] | None:
    """Parse a text control message; None if it is not a JSON object."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def ready(call_id: str) -> dict[str, Any]:
    return {"type": "ready", "call_id": call_id}


def clear() -> dict[str, Any]:
    return {"type": "clear"}


def end_call(reason: str) -> dict[str, Any]:
    return {"type": "end_call", "reason": reason}


def error(message: str) -> dict[str, Any]:
    return {"type": "error", "message": message}
