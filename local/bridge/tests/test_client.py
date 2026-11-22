import asyncio
import json

import pytest
from websockets.asyncio.server import serve

from carwash_bridge.client import BridgeCall, BridgeError, CallRequest


class Recorder:
    def __init__(self) -> None:
        self.audio: list[bytes] = []
        self.clears = 0
        self.ends: list[str] = []
        self.errors: list[str] = []

    def call(self, url: str, token: str = "tok") -> BridgeCall:
        return BridgeCall(
            url,
            token,
            "test-bridge",
            on_audio=self.audio.append,
            on_clear=lambda: setattr(self, "clears", self.clears + 1),
            on_end_call=self.ends.append,
            on_error=self.errors.append,
        )


async def run_server(handler):
    server = await serve(handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    return server, f"ws://127.0.0.1:{port}/ws/local-bridge"


async def test_handshake_audio_and_control_messages() -> None:
    received: dict = {}

    async def handler(ws):
        received["auth"] = ws.request.headers.get("Authorization")
        received["start"] = json.loads(await ws.recv())
        await ws.send(json.dumps({"type": "ready", "call_id": received["start"]["call_id"]}))
        await ws.send(b"\x01\x00" * 4)
        await ws.send(json.dumps({"type": "clear"}))
        await ws.send(json.dumps({"type": "end_call", "reason": "agent_done"}))
        received["audio_in"] = await ws.recv()
        received["stop"] = json.loads(await ws.recv())

    server, url = await run_server(handler)
    rec = Recorder()
    call = rec.call(url)
    async with server:
        call_id = await call.start(CallRequest("inbound", "+919845012345"))
        await call.send_audio(b"\x02\x00" * 320)
        for _ in range(100):
            if rec.ends:
                break
            await asyncio.sleep(0.02)
        await call.stop("operator_hangup")
    assert received["auth"] == "Bearer tok"
    assert received["start"]["protocol"] == 1 and received["start"]["call_id"] == call_id
    assert received["start"]["caller_number"] == "+919845012345"
    assert received["audio_in"] == b"\x02\x00" * 320
    assert received["stop"] == {"type": "stop", "reason": "operator_hangup"}
    assert rec.audio == [b"\x01\x00" * 4] and rec.clears == 1 and rec.ends == ["agent_done"]


async def test_bad_token_gives_clear_error() -> None:
    async def handler(ws):
        await ws.close(4401)

    server, url = await run_server(handler)
    async with server:
        with pytest.raises(BridgeError, match="token"):
            await Recorder().call(url).start(CallRequest())


async def test_no_provider_gives_clear_error() -> None:
    async def handler(ws):
        await ws.recv()
        await ws.send(json.dumps({"type": "error", "message": "no provider"}))
        await ws.close(4503)

    server, url = await run_server(handler)
    async with server:
        with pytest.raises(BridgeError, match="no provider"):
            await Recorder().call(url).start(CallRequest())


async def test_backend_down_gives_clear_error() -> None:
    with pytest.raises(BridgeError, match="Cannot reach"):
        await Recorder().call("ws://127.0.0.1:9/ws/local-bridge").start(CallRequest())


async def test_server_closing_sets_closed_event() -> None:
    async def handler(ws):
        await ws.recv()
        await ws.send(json.dumps({"type": "ready", "call_id": "x"}))
        await ws.close()

    server, url = await run_server(handler)
    call = Recorder().call(url)
    async with server:
        await call.start(CallRequest())
        await asyncio.wait_for(call.closed.wait(), timeout=3)
