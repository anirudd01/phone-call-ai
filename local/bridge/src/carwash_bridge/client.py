"""WebSocket client for the bridge protocol v1 (see local/docs/bridge-protocol.md)."""

from __future__ import annotations

import asyncio
import contextlib
import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass

from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed, InvalidHandshake

PROTOCOL = 1


class BridgeError(RuntimeError):
    """Raised for problems the operator should see as one clear line."""


@dataclass
class CallRequest:
    direction: str = "inbound"
    caller_number: str | None = None
    outbound_job_id: int | None = None
    call_id: str | None = None


class BridgeCall:
    """One call: connect, handshake, then exchange audio and control messages."""

    def __init__(
        self,
        url: str,
        token: str,
        bridge_id: str,
        on_audio: Callable[[bytes], None],
        on_clear: Callable[[], None],
        on_end_call: Callable[[str], None],
        on_error: Callable[[str], None] = lambda _m: None,
    ) -> None:
        self._url = url
        self._token = token
        self._bridge_id = bridge_id
        self._on_audio = on_audio
        self._on_clear = on_clear
        self._on_end_call = on_end_call
        self._on_error = on_error
        self._ws: ClientConnection | None = None
        self._reader: asyncio.Task[None] | None = None
        self.call_id = ""
        self.close_code: int | None = None
        self.closed = asyncio.Event()

    async def start(self, req: CallRequest) -> str:
        self.call_id = req.call_id or str(uuid.uuid4())
        try:
            self._ws = await connect(
                self._url,
                additional_headers={"Authorization": f"Bearer {self._token}"},
                open_timeout=10,
                max_size=2**20,
            )
        except (OSError, TimeoutError) as exc:
            raise BridgeError(f"Cannot reach the backend at {self._url}: is it running?") from exc
        except InvalidHandshake as exc:
            raise BridgeError(f"The backend refused the connection: {exc}") from exc
        try:
            await self._ws.send(
                json.dumps(
                    {
                        "type": "start",
                        "protocol": PROTOCOL,
                        "call_id": self.call_id,
                        "direction": req.direction,
                        "caller_number": req.caller_number,
                        "outbound_job_id": req.outbound_job_id,
                        "bridge_id": self._bridge_id,
                    }
                )
            )
            async with asyncio.timeout(10):
                first = await self._ws.recv()
        except ConnectionClosed as exc:
            raise BridgeError(self._explain_close(exc)) from exc
        except TimeoutError as exc:
            raise BridgeError("The backend did not answer the start message.") from exc
        message = json.loads(first) if isinstance(first, str) else {}
        if message.get("type") == "error":
            await self._ws.close()
            raise BridgeError(f"Backend error: {message.get('message')}")
        if message.get("type") != "ready":
            await self._ws.close()
            raise BridgeError(f"Unexpected first message from the backend: {message}")
        self._reader = asyncio.create_task(self._read_loop())
        return self.call_id

    @staticmethod
    def _explain_close(exc: ConnectionClosed) -> str:
        code = exc.rcvd.code if exc.rcvd else None
        reasons = {
            4401: "The backend rejected the token (check BRIDGE_TOKEN).",
            4400: "The backend rejected the start message.",
            4503: "The backend has no voice provider (is OPENAI_API_KEY set?).",
        }
        return reasons.get(code, f"The backend closed the connection (code {code}).")

    async def _read_loop(self) -> None:
        assert self._ws is not None
        try:
            async for msg in self._ws:
                if isinstance(msg, bytes):
                    self._on_audio(msg)
                    continue
                data = json.loads(msg)
                kind = data.get("type")
                if kind == "clear":
                    self._on_clear()
                elif kind == "end_call":
                    self._on_end_call(str(data.get("reason", "")))
                elif kind == "error":
                    self._on_error(str(data.get("message", "")))
        except ConnectionClosed:
            pass
        finally:
            self.close_code = self._ws.close_code
            self.closed.set()

    async def send_audio(self, frame: bytes) -> None:
        if self._ws is None or self.closed.is_set():
            return
        with contextlib.suppress(ConnectionClosed):
            await self._ws.send(frame)

    async def stop(self, reason: str = "operator_hangup") -> None:
        """Tell the backend the call is over and close the socket."""
        if self._ws is None:
            return
        with contextlib.suppress(ConnectionClosed):
            if not self.closed.is_set():
                await self._ws.send(json.dumps({"type": "stop", "reason": reason}))
            await self._ws.close()
        if self._reader is not None:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await asyncio.wait_for(self._reader, timeout=3)
