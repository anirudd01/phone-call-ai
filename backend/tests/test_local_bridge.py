import json
import math
import struct
import time
import uuid
import wave
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from carwash_voice.config import Settings
from carwash_voice.db.models import Call
from carwash_voice.main import create_app
from carwash_voice.transports.local import protocol
from tests.fakes import EchoProvider

FRAME_BYTES = 640  # 20 ms of 16 kHz mono PCM16
AUTH = {"Authorization": "Bearer test-bridge"}


def start_msg(call_id: str | None = None, **over: object) -> str:
    msg = {
        "type": "start",
        "protocol": 1,
        "call_id": call_id or str(uuid.uuid4()),
        "direction": "inbound",
        "caller_number": "+919845012345",
        "outbound_job_id": None,
        "bridge_id": "test-bridge",
    } | over
    return json.dumps(msg)


@pytest.fixture
def wav_fixture(tmp_path: Path) -> Path:
    """One second of a 440 Hz tone as a 16 kHz mono WAV (stands in for a recorded complaint)."""
    path = tmp_path / "complaint.wav"
    samples = [int(8000 * math.sin(2 * math.pi * 440 * i / 16000)) for i in range(16000)]
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(struct.pack(f"<{len(samples)}h", *samples))
    return path


def wav_frames(path: Path) -> Iterator[bytes]:
    with wave.open(str(path), "rb") as w:
        data = w.readframes(w.getnframes())
    for i in range(0, len(data) - FRAME_BYTES + 1, FRAME_BYTES):
        yield data[i : i + FRAME_BYTES]


def make_client(settings: Settings, provider: EchoProvider | None) -> TestClient:
    return TestClient(create_app(settings, provider))


def call_row(c: TestClient, call_id: str) -> Call | None:
    with c.app.state.session_factory() as s:
        return s.get(Call, call_id)


def wait_for(cond: Callable[[], bool], timeout: float = 8.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.05)
    return False


def wait_finalised(c: TestClient, call_id: str) -> Call:
    assert wait_for(lambda: (r := call_row(c, call_id)) is not None and r.ended_at is not None), (
        "call row was not finalised"
    )
    row = call_row(c, call_id)
    assert row is not None
    return row


def expect_close(ws, code: int) -> None:
    """Read messages until the server closes the socket, and check the close code."""
    for _ in range(50):
        msg = ws.receive()  # the test client returns the close as a message
        if msg["type"] == "websocket.close":
            assert msg["code"] == code
            return
    raise AssertionError("socket was not closed")


def test_happy_path_streams_wav_and_gets_audio_back(settings: Settings, wav_fixture: Path) -> None:
    call_id = str(uuid.uuid4())
    with make_client(settings, EchoProvider()) as c:
        with c.websocket_connect("/ws/local-bridge", headers=AUTH) as ws:
            ws.send_text(start_msg(call_id))
            assert json.loads(ws.receive_text()) == {"type": "ready", "call_id": call_id}
            for frame in wav_frames(wav_fixture):
                ws.send_bytes(frame)
            received = 0
            while received < 10 * FRAME_BYTES:
                data = ws.receive_bytes()
                assert len(data) > 0 and len(data) % 2 == 0
                received += len(data)
            ws.send_text(json.dumps({"type": "stop", "reason": "operator_hangup"}))
        row = wait_finalised(c, call_id)
    assert row.end_reason == "operator_hangup"
    assert row.caller_number == "+919845012345"
    assert row.direction.value == "inbound"


def test_agent_end_call_sends_end_call_then_closes(settings: Settings, wav_fixture: Path) -> None:
    call_id = str(uuid.uuid4())
    with make_client(settings, EchoProvider(end_after_frames=5, end_reason="agent_done")) as c:
        with c.websocket_connect("/ws/local-bridge", headers=AUTH) as ws:
            ws.send_text(start_msg(call_id))
            assert json.loads(ws.receive_text())["type"] == "ready"
            for frame in wav_frames(wav_fixture):
                ws.send_bytes(frame)
            seen_end = None
            for _ in range(200):
                msg = ws.receive()
                if msg["type"] == "websocket.close":
                    break
                if msg.get("text"):
                    seen_end = json.loads(msg["text"])
                    if seen_end["type"] == "end_call":
                        break
            assert seen_end == {"type": "end_call", "reason": "agent_done"}
        row = wait_finalised(c, call_id)
    assert row.end_reason == "agent_done"


def test_bad_token_closes_4401(settings: Settings) -> None:
    with make_client(settings, EchoProvider()) as c:
        for headers in ({}, {"Authorization": "Bearer wrong"}, {"Authorization": "test-bridge"}):
            with c.websocket_connect("/ws/local-bridge", headers=headers) as ws:
                expect_close(ws, protocol.CLOSE_UNAUTHORIZED)


def test_token_in_url_is_not_accepted(settings: Settings) -> None:
    with make_client(settings, EchoProvider()) as c:
        with c.websocket_connect("/ws/local-bridge?token=test-bridge") as ws:
            expect_close(ws, protocol.CLOSE_UNAUTHORIZED)


def test_missing_start_times_out(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(protocol, "START_TIMEOUT_SECS", 0.3)
    with make_client(settings, EchoProvider()) as c:
        with c.websocket_connect("/ws/local-bridge", headers=AUTH) as ws:
            expect_close(ws, protocol.CLOSE_BAD_START)


@pytest.mark.parametrize(
    "first",
    [
        "not json",
        json.dumps({"type": "stop"}),
        start_msg(protocol=2),
        start_msg(direction="sideways"),
    ],
)
def test_bad_start_rejected(settings: Settings, first: str) -> None:
    with make_client(settings, EchoProvider()) as c:
        with c.websocket_connect("/ws/local-bridge", headers=AUTH) as ws:
            ws.send_text(first)
            expect_close(ws, protocol.CLOSE_BAD_START)


def test_abrupt_disconnect_still_finalises_call(settings: Settings) -> None:
    call_id = str(uuid.uuid4())
    with make_client(settings, EchoProvider()) as c:
        with c.websocket_connect("/ws/local-bridge", headers=AUTH) as ws:
            ws.send_text(start_msg(call_id))
            assert json.loads(ws.receive_text())["type"] == "ready"
            ws.send_bytes(b"\x00" * FRAME_BYTES)
            # leave the block without sending "stop": the socket just closes
        row = wait_finalised(c, call_id)
    assert row.end_reason == "remote_hangup"


def test_max_call_seconds_ends_the_call(settings: Settings) -> None:
    call_id = str(uuid.uuid4())
    short = settings.model_copy(update={"max_call_seconds": 1})
    with make_client(short, EchoProvider()) as c:
        with c.websocket_connect("/ws/local-bridge", headers=AUTH) as ws:
            ws.send_text(start_msg(call_id))
            assert json.loads(ws.receive_text())["type"] == "ready"
            row = wait_finalised(c, call_id)
    assert row.end_reason == "max_duration"


def test_no_provider_closes_4503(settings: Settings) -> None:
    with make_client(settings, None) as c:
        with c.websocket_connect("/ws/local-bridge", headers=AUTH) as ws:
            ws.send_text(start_msg())
            expect_close(ws, protocol.CLOSE_UNAVAILABLE)


def test_route_absent_when_disabled(settings: Settings) -> None:
    off = settings.model_copy(update={"enable_local_bridge": False})
    with make_client(off, EchoProvider()) as c, pytest.raises(WebSocketDisconnect):
        with c.websocket_connect("/ws/local-bridge", headers=AUTH):
            pass


def test_calls_visible_through_admin_api(settings: Settings) -> None:
    call_id = str(uuid.uuid4())
    with make_client(settings, EchoProvider()) as c:
        with c.websocket_connect("/ws/local-bridge", headers=AUTH) as ws:
            ws.send_text(start_msg(call_id))
            ws.receive_text()
            ws.send_text(json.dumps({"type": "stop", "reason": "operator_hangup"}))
        wait_finalised(c, call_id)
        r = c.get(f"/api/calls/{call_id}", headers={"X-Admin-Key": "test-admin"})
        assert r.status_code == 200 and r.json()["end_reason"] == "operator_hangup"
