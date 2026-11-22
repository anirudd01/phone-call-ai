import base64
import json
import time
from collections.abc import Iterator
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient
from pipecat.audio import g711
from pipecat.serializers.plivo import PlivoFrameSerializer
from plivo.utils.signature_v3 import construct_post_url, get_signature_v3
from starlette.websockets import WebSocketDisconnect

from carwash_voice.config import Settings
from carwash_voice.db.models import Call
from carwash_voice.main import create_app
from carwash_voice.transports.plivo.endpoint import e164, parse_extra_headers, ws_url
from tests.fakes import EchoProvider

BASE = "https://voice.example.com"
TOKEN = "plivo-token"
SECRET = "wsSecret123"
ANSWER = f"{BASE}/plivo/answer"


@pytest.fixture
def plivo_settings(settings: Settings) -> Settings:
    return settings.model_copy(
        update={
            "public_base_url": BASE,
            "plivo_auth_id": "MAXXXXXXXX",
            "plivo_auth_token": TOKEN,
            "plivo_ws_secret": SECRET,
        }
    )


@pytest.fixture(autouse=True)
def no_real_hangup(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake(self: PlivoFrameSerializer) -> None:  # never call Plivo from tests
        return None

    monkeypatch.setattr(PlivoFrameSerializer, "_hang_up_call", fake)


@pytest.fixture
def plivo_client(plivo_settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(plivo_settings, provider=EchoProvider())) as c:
        yield c


def signed_post(
    client: TestClient, form: dict[str, str], query: str = "", token: str = TOKEN, nonce: str = "n1"
):
    url = ANSWER + (f"?{query}" if query else "")
    base = construct_post_url(url, dict(form)).decode()
    sig = get_signature_v3(token.encode(), base, nonce.encode()).decode()
    headers = {"X-Plivo-Signature-V3": sig, "X-Plivo-Signature-V3-Nonce": nonce}
    return client.post(
        "/plivo/answer" + (f"?{query}" if query else ""),
        content=urlencode(form),
        headers={**headers, "Content-Type": "application/x-www-form-urlencoded"},
    )


# --- helpers -----------------------------------------------------------------------------------


def test_helpers() -> None:
    assert e164("919845012345") == "+919845012345"
    assert e164("+919845012345") == "+919845012345" and e164(None) is None and e164("") is None
    assert parse_extra_headers("direction=outbound;job_id=7") == {
        "direction": "outbound",
        "job_id": "7",
    }
    assert parse_extra_headers({"a": 1}) == {"a": "1"} and parse_extra_headers(None) == {}


def test_ws_url_uses_wss_and_secret(plivo_settings: Settings) -> None:
    assert ws_url(plivo_settings) == f"wss://voice.example.com/ws/plivo/{SECRET}"


# --- answer URL --------------------------------------------------------------------------------


def test_answer_returns_stream_xml_for_inbound(plivo_client: TestClient) -> None:
    r = signed_post(plivo_client, {"CallUUID": "u1", "From": "919845012345", "To": "8012345678"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/xml")
    assert 'bidirectional="true"' in r.text and 'keepCallAlive="true"' in r.text
    assert 'contentType="audio/x-mulaw;rate=8000"' in r.text
    assert f"wss://voice.example.com/ws/plivo/{SECRET}" in r.text
    assert "direction=inbound;customer=+919845012345" in r.text


def test_answer_for_outbound_uses_to_number_and_job(plivo_client: TestClient) -> None:
    r = signed_post(
        plivo_client,
        {"CallUUID": "u2", "Direction": "outbound", "From": "8012345678", "To": "919845012345"},
        query="job_id=7",
    )
    assert "direction=outbound;customer=+919845012345;job_id=7" in r.text


def test_answer_rejects_bad_or_missing_signature(plivo_client: TestClient) -> None:
    assert signed_post(plivo_client, {"From": "1"}, token="wrong").status_code == 403
    assert plivo_client.post("/plivo/answer", data={"From": "1"}).status_code == 403


def test_answer_503_when_not_configured(client: TestClient) -> None:
    assert client.post("/plivo/answer", data={"From": "1"}).status_code == 503


# --- media websocket ---------------------------------------------------------------------------


def start_event(call_id: str, extra: str = "direction=inbound;customer=+919845012345") -> str:
    return json.dumps(
        {
            "event": "start",
            "sequenceNumber": 0,
            "start": {"callId": call_id, "streamId": "stream-1", "accountId": "x"},
            "extra_headers": extra,
        }
    )


def media_event() -> str:
    pcm = bytes(320)  # 20 ms of silence at 8 kHz
    payload = base64.b64encode(g711.pcm_to_ulaw(pcm)).decode()
    return json.dumps(
        {
            "event": "media",
            "streamId": "stream-1",
            "media": {"track": "inbound", "payload": payload},
        }
    )


def wait_row(c: TestClient, call_id: str, finished: bool = True) -> Call | None:
    end = time.monotonic() + 8
    while time.monotonic() < end:
        with c.app.state.session_factory() as s:
            row = s.get(Call, call_id)
            if row is not None and (row.ended_at is not None or not finished):
                return row
        time.sleep(0.05)
    return None


def test_media_socket_runs_a_call_and_plays_audio_back(plivo_client: TestClient) -> None:
    call_id = "7b0e1f4a-1111-4222-8333-444455556666"
    with plivo_client.websocket_connect(f"/ws/plivo/{SECRET}") as ws:
        ws.send_text(start_event(call_id))
        for _ in range(30):
            ws.send_text(media_event())
        first = json.loads(ws.receive_text())
        assert first["event"] == "playAudio" and first["streamId"] == "stream-1"
        assert first["media"]["contentType"] == "audio/x-mulaw"
    row = wait_row(plivo_client, call_id)
    assert row is not None and row.ended_at is not None
    assert row.direction.value == "inbound" and row.caller_number == "+919845012345"


def test_media_socket_carries_outbound_job_id(plivo_client: TestClient) -> None:
    from carwash_voice.domain import customers, outbound

    with plivo_client.app.state.session_factory() as s:
        c = customers.upsert_customer(s, name="Ravi", phone="9845012345")
        job = outbound.create_job(s, "Your car is ready", customer_id=c.id)
        job_id = job.id
    call_id = "7b0e1f4a-2222-4222-8333-444455556666"
    extra = f"direction=outbound;customer=+919845012345;job_id={job_id}"
    with plivo_client.websocket_connect(f"/ws/plivo/{SECRET}") as ws:
        ws.send_text(start_event(call_id, extra))
        ws.send_text(media_event())
    row = wait_row(plivo_client, call_id, finished=False)
    assert row is not None and row.direction.value == "outbound"
    assert row.outbound_job_id == job_id


def test_wrong_secret_is_closed_4401(plivo_client: TestClient) -> None:
    with plivo_client.websocket_connect("/ws/plivo/nope") as ws:
        msg = ws.receive()
        assert msg["type"] == "websocket.close" and msg["code"] == 4401


def test_bad_first_message_is_closed_4400(plivo_client: TestClient) -> None:
    with plivo_client.websocket_connect(f"/ws/plivo/{SECRET}") as ws:
        ws.send_text("not json")
        msg = ws.receive()
        assert msg["type"] == "websocket.close" and msg["code"] == 4400


def test_no_provider_is_closed_4503(plivo_settings: Settings) -> None:
    with TestClient(create_app(plivo_settings)) as c:
        with c.websocket_connect(f"/ws/plivo/{SECRET}") as ws:
            ws.send_text(start_event("7b0e1f4a-3333-4222-8333-444455556666"))
            msg = ws.receive()
            assert msg["type"] == "websocket.close" and msg["code"] == 4503


def test_secret_is_never_accepted_when_unset(client: TestClient) -> None:
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/plivo/") as ws:
            ws.receive()
