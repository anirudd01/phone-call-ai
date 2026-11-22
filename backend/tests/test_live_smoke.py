"""Live smoke test: a real OpenAI Realtime session. Skipped by default.

Run with:  uv run pytest -m live -s
Needs OPENAI_API_KEY and OPENAI_REALTIME_MODEL in backend/.env. Costs a little money.
"""

import json
import time
import uuid
import wave
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from carwash_voice.config import Settings
from carwash_voice.db.models import Call, Ticket
from carwash_voice.main import create_app

pytestmark = pytest.mark.live

FIXTURES = Path(__file__).parent / "fixtures"
FRAME = 640  # 20 ms at 16 kHz mono PCM16


@pytest.fixture
def live_settings(tmp_path: Path) -> Settings:
    base = Settings(_env_file=".env")
    if not base.openai_api_key or not base.openai_realtime_model:
        pytest.skip("OPENAI_API_KEY / OPENAI_REALTIME_MODEL not set in backend/.env")
    return base.model_copy(
        update={
            "database_url": f"sqlite:///{(tmp_path / 'live.db').as_posix()}",
            "recordings_dir": str(tmp_path / "rec"),
            "admin_api_key": "live-admin",
            "bridge_token": "live-bridge",
            "enable_local_bridge": True,
            "max_call_seconds": 120,
            "log_level": "DEBUG",
        }
    )


def _frames(name: str) -> list[bytes]:
    with wave.open(str(FIXTURES / name), "rb") as w:
        assert w.getframerate() == 16000 and w.getnchannels() == 1
        data = w.readframes(w.getnframes())
    return [data[i : i + FRAME] for i in range(0, len(data) - FRAME + 1, FRAME)]


def test_complaint_creates_ticket(live_settings: Settings) -> None:
    call_id = str(uuid.uuid4())
    with TestClient(create_app(live_settings)) as client:
        factory = client.app.state.session_factory

        def ticket() -> Ticket | None:
            with factory() as s:
                return s.scalar(select(Ticket))

        with client.websocket_connect(
            "/ws/local-bridge", headers={"Authorization": "Bearer live-bridge"}
        ) as ws:
            ws.send_text(
                json.dumps(
                    {
                        "type": "start",
                        "protocol": 1,
                        "call_id": call_id,
                        "direction": "inbound",
                        "caller_number": "+919845012345",
                        "outbound_job_id": None,
                        "bridge_id": "pytest",
                    }
                )
            )
            assert json.loads(ws.receive_text())["type"] == "ready"
            time.sleep(4)  # let the agent greet first, as it would on a real call

            def speak(name: str) -> None:
                for frame in _frames(name):
                    ws.send_bytes(frame)
                    time.sleep(0.02)  # real time, like a phone line

            speak("complaint_en.wav")
            started = time.monotonic()
            confirm_at = [20, 45]  # if the agent still waits for a yes, say it
            while ticket() is None and time.monotonic() - started < 75:
                if confirm_at and time.monotonic() - started >= confirm_at[0]:
                    confirm_at.pop(0)
                    speak("confirm_en.wav")
                else:
                    ws.send_bytes(b"\x00" * FRAME)  # keep the line open with silence
                    time.sleep(0.02)
            found = ticket()
            ws.send_text(json.dumps({"type": "stop", "reason": "operator_hangup"}))

        assert found is not None, "the agent did not create a ticket within 75 s"
        assert found.category.value in {"quality", "other"}
        with factory() as s:
            call = s.get(Call, call_id)
        assert call is not None
        print(f"\nTicket {found.public_ref}: {found.category.value} - {found.description}")
