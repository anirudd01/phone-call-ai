import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from carwash_voice.config import Settings

EXPECTED_TABLES = {"customers", "tickets", "ticket_events", "calls", "outbound_jobs"}


def test_healthz_ok(client: TestClient) -> None:
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "database": "ok"}


def test_migrations_create_tables(client: TestClient, settings: Settings) -> None:
    path = Path(settings.sqlalchemy_url.removeprefix("sqlite:///"))
    with sqlite3.connect(path) as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert tables >= EXPECTED_TABLES


def test_healthz_reports_db_down(client: TestClient) -> None:
    class Broken:
        def connect(self) -> None:
            raise RuntimeError("boom")

    client.app.state.engine = Broken()
    r = client.get("/healthz")
    assert r.status_code == 503
    assert r.json()["database"] == "down"
