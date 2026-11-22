from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from carwash_voice.config import Settings
from carwash_voice.domain import calls, customers, tickets
from carwash_voice.main import create_app
from carwash_voice.voice.recording import LocalRecordingStore
from tests.conftest import ADMIN, BRIDGE


def _ticket(session: Session):
    c = customers.upsert_customer(session, name="Ravi", phone="9845012345")
    return c, tickets.create_ticket(session, c.id, "quality", "Dirty seats")


def test_admin_auth_required(client: TestClient) -> None:
    assert client.get("/api/tickets").status_code == 401
    assert client.get("/api/tickets", headers={"X-Admin-Key": "wrong"}).status_code == 401
    assert client.get("/api/tickets", headers=BRIDGE).status_code == 401
    assert client.get("/api/tickets", headers=ADMIN).status_code == 200


def test_admin_key_not_configured_is_503(settings: Settings) -> None:
    s = settings.model_copy(update={"admin_api_key": ""})
    with TestClient(create_app(s)) as c:
        assert c.get("/api/tickets", headers=ADMIN).status_code == 503


def test_ticket_list_get_patch(client: TestClient, session: Session) -> None:
    c, t = _ticket(session)
    other = tickets.create_ticket(session, c.id, "billing", "overcharged")
    tickets.request_callback(session, other, "wants manager")

    r = client.get("/api/tickets", headers=ADMIN)
    assert {x["public_ref"] for x in r.json()} == {t.public_ref, other.public_ref}

    r = client.get("/api/tickets?status=callback_requested", headers=ADMIN)
    assert [x["public_ref"] for x in r.json()] == [other.public_ref]
    assert client.get("/api/tickets?status=bogus", headers=ADMIN).status_code == 422

    r = client.get(f"/api/tickets/{t.public_ref}", headers=ADMIN)
    assert r.status_code == 200 and r.json()["events"][0]["kind"] == "created"
    assert client.get("/api/tickets/CW-00000", headers=ADMIN).status_code == 404
    assert client.get("/api/tickets/banana", headers=ADMIN).status_code == 422

    r = client.patch(
        f"/api/tickets/{t.public_ref}",
        headers=ADMIN,
        json={"status": "resolved", "priority": "high", "note": "Refunded"},
    )
    body = r.json()
    assert r.status_code == 200 and body["status"] == "resolved" and body["priority"] == "high"
    assert [e["kind"] for e in body["events"]] == ["created", "status_changed", "note"]
    assert body["events"][1]["actor"] == "staff"


def test_get_customer(client: TestClient, session: Session) -> None:
    c, _ = _ticket(session)
    r = client.get(f"/api/customers/{c.id}", headers=ADMIN)
    assert r.json()["phone"] == "+919845012345"
    assert client.get("/api/customers/999", headers=ADMIN).status_code == 404


def test_calls_and_audio(
    client: TestClient, session: Session, settings: Settings, tmp_path: Path
) -> None:
    cid = "22222222-2222-4222-8222-222222222222"
    calls.create_call(session, cid, "inbound", "+919845012345")
    rel = LocalRecordingStore(settings.recordings_dir).save(cid, b"RIFFfake")
    calls.finalize_call(
        session, cid, "operator_hangup", transcript=[{"role": "user", "text": "hi", "ts": 1}]
    )
    r = client.get("/api/calls", headers=ADMIN)
    assert r.json()[0]["transcript"][0]["text"] == "hi"
    assert client.get(f"/api/calls/{cid}", headers=ADMIN).status_code == 200
    assert client.get("/api/calls/nope", headers=ADMIN).status_code == 404

    assert client.get(f"/api/calls/{cid}/audio", headers=ADMIN).status_code == 404  # none yet
    calls.finalize_call(session, cid, "x", audio_path=rel)
    r = client.get(f"/api/calls/{cid}/audio", headers=ADMIN)
    assert r.status_code == 200 and r.content == b"RIFFfake"
    calls.finalize_call(session, cid, "x", audio_path="../../outside.wav")
    assert client.get(f"/api/calls/{cid}/audio", headers=ADMIN).status_code == 404


def test_outbound_jobs_admin_and_bridge(client: TestClient, session: Session) -> None:
    _, t = _ticket(session)
    r = client.post(
        "/api/outbound-jobs",
        headers=ADMIN,
        json={"ticket_ref": t.public_ref, "message": "Refund approved"},
    )
    assert r.status_code == 201
    job = r.json()
    assert job["status"] == "queued" and job["phone"] == "+919845012345"
    r = client.post("/api/outbound-jobs", headers=ADMIN, json={"message": "x"})
    assert r.status_code == 422
    r = client.post(
        "/api/outbound-jobs", headers=ADMIN, json={"message": "x", "ticket_ref": "CW-00000"}
    )
    assert r.status_code == 404
    listed = client.get("/api/outbound-jobs?status=queued", headers=ADMIN).json()
    assert listed[0]["id"] == job["id"]

    # bridge endpoints use the bridge token, not the admin key
    assert client.get("/api/bridge/outbound-jobs/next", headers=ADMIN).status_code == 401
    r = client.get("/api/bridge/outbound-jobs/next", headers=BRIDGE)
    assert r.status_code == 200 and r.json()["id"] == job["id"]

    r = client.post(
        f"/api/bridge/outbound-jobs/{job['id']}/status", headers=BRIDGE, json={"status": "dialling"}
    )
    assert r.json()["status"] == "dialling"
    assert client.get("/api/bridge/outbound-jobs/next", headers=BRIDGE).status_code == 204
    r = client.post(
        "/api/bridge/outbound-jobs/999/status", headers=BRIDGE, json={"status": "failed"}
    )
    assert r.status_code == 404


def test_openapi_lists_endpoints(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    for p in (
        "/api/tickets",
        "/api/tickets/{public_ref}",
        "/api/customers/{customer_id}",
        "/api/calls",
        "/api/calls/{call_id}/audio",
        "/api/outbound-jobs",
        "/api/bridge/outbound-jobs/next",
        "/api/bridge/outbound-jobs/{job_id}/status",
        "/healthz",
    ):
        assert p in paths
    assert client.get("/docs").status_code == 200
