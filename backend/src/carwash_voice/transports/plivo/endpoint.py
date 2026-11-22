"""Plivo phone transport: an Answer URL that returns <Stream> XML, and the media WebSocket.

Flow: a call reaches Plivo -> Plivo POSTs /plivo/answer -> we reply with XML telling Plivo to
open a WebSocket to /ws/plivo/<secret> -> the WebSocket sends a `start` event, then audio.
Outbound calls use the same two endpoints (the Answer URL carries the job id).
"""

from __future__ import annotations

import asyncio
import json
import secrets
import time
from html import escape
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from fastapi import APIRouter, FastAPI, Request, Response, WebSocket
from loguru import logger
from pipecat.serializers.plivo import PlivoFrameSerializer
from pipecat.transports.websocket.fastapi import FastAPIWebsocketParams, FastAPIWebsocketTransport
from sqlalchemy.orm import Session

from carwash_voice.config import Settings
from carwash_voice.db.models import JobStatus
from carwash_voice.db.session import run_db
from carwash_voice.domain import outbound
from carwash_voice.transports.plivo.signature import verify_signature
from carwash_voice.voice.session import CallContext, CallHandle, CallResources, run_call

router = APIRouter()

START_TIMEOUT_SECS = 10
CLOSE_UNAUTHORIZED = 4401
CLOSE_BAD_START = 4400
CLOSE_UNAVAILABLE = 4503
CONTENT_TYPE = "audio/x-mulaw;rate=8000"  # must match what PlivoFrameSerializer sends


PENDING_TTL_SECS = 300


class PendingCalls:
    """What /plivo/answer learned about each call, kept until its media socket opens.

    Keyed by Plivo's CallUUID; the socket's start event carries the same id as `callId`. This
    avoids relying on how Plivo echoes `extraHeaders` back (unverified). In memory, which is
    fine for one server process; entries expire after PENDING_TTL_SECS.
    """

    def __init__(self, ttl: float = PENDING_TTL_SECS) -> None:
        self._ttl = ttl
        self._items: dict[str, tuple[float, dict[str, str]]] = {}

    def put(self, call_uuid: str, info: dict[str, str]) -> None:
        now = time.monotonic()
        self._items = {k: v for k, v in self._items.items() if v[0] > now}
        self._items[call_uuid] = (now + self._ttl, dict(info))

    def pop(self, call_uuid: str) -> dict[str, str] | None:
        item = self._items.pop(call_uuid, None)
        if item is None or item[0] < time.monotonic():
            return None
        return item[1]


def pending_calls(app: FastAPI) -> PendingCalls:
    store = getattr(app.state, "plivo_pending", None)
    if store is None:
        store = app.state.plivo_pending = PendingCalls()
    return store


def ws_url(settings: Settings) -> str:
    """The public wss:// URL Plivo should open, with the secret as the last path segment."""
    parts = urlsplit(settings.public_base_url.rstrip("/"))
    scheme = "wss" if parts.scheme == "https" else "ws"
    path = f"{parts.path}/ws/plivo/{settings.plivo_ws_secret}"
    return urlunsplit((scheme, parts.netloc, path, "", ""))


def public_url(settings: Settings, path: str, query: str = "") -> str:
    """The URL Plivo used to reach us (needed to check its signature behind a proxy)."""
    base = settings.public_base_url.rstrip("/")
    return f"{base}{path}" + (f"?{query}" if query else "")


def stream_xml(settings: Settings, extra: dict[str, str]) -> str:
    headers = ";".join(f"{k}={v}" for k, v in extra.items())
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<Response>"
        f'<Stream bidirectional="true" keepCallAlive="true" contentType="{CONTENT_TYPE}" '
        f'extraHeaders="{escape(headers, quote=True)}">{escape(ws_url(settings))}</Stream>'
        "</Response>"
    )


def e164(number: str | None) -> str | None:
    """Plivo gives numbers like 919845012345; make them +919845012345."""
    if not number:
        return None
    number = number.strip()
    return number if number.startswith("+") or not number.isdigit() else f"+{number}"


def parse_extra_headers(raw: Any) -> dict[str, str]:
    """`extra_headers` arrives as "k=v;k=v" (or already a dict)."""
    if isinstance(raw, dict):
        return {str(k): str(v) for k, v in raw.items()}
    result: dict[str, str] = {}
    for part in str(raw or "").split(";"):
        key, sep, value = part.partition("=")
        if sep and key.strip():
            result[key.strip()] = value.strip()
    return result


@router.post("/plivo/answer")
async def answer(request: Request) -> Response:
    settings: Settings = request.app.state.settings
    if not settings.plivo_enabled:
        return Response(status_code=503, content="Plivo is not configured")
    form = {k: str(v) for k, v in (await request.form()).items()}
    query = request.url.query
    ok = verify_signature(
        "POST",
        public_url(settings, request.url.path, query),
        request.headers.get("x-plivo-signature-v3-nonce", ""),
        request.headers.get("x-plivo-signature-v3", ""),
        settings.plivo_auth_token,
        form,
    )
    if not ok:
        logger.warning("Rejected /plivo/answer: bad or missing Plivo signature")
        return Response(status_code=403, content="bad signature")

    direction = "outbound" if form.get("Direction", "").lower() == "outbound" else "inbound"
    job_id = request.query_params.get("job_id", "")
    # For an inbound call the customer is "From"; for our outbound call they are "To".
    customer = form.get("To") if direction == "outbound" else form.get("From")
    extra = {"direction": direction, "customer": e164(customer) or ""}
    if direction == "outbound" and job_id.isdigit():
        extra["job_id"] = job_id
    call_uuid = form.get("CallUUID", "")
    if call_uuid:
        pending_calls(request.app).put(call_uuid, extra)
    logger.info("Plivo answer: {} call, call {}", direction, call_uuid or "?")
    return Response(content=stream_xml(settings, extra), media_type="application/xml")


UNANSWERED = {
    "no-answer": JobStatus.NO_ANSWER,
    "busy": JobStatus.NO_ANSWER,
    "timeout": JobStatus.NO_ANSWER,
    "cancel": JobStatus.NO_ANSWER,
    "failed": JobStatus.FAILED,
}


@router.post("/plivo/hangup")
async def hangup(request: Request) -> Response:
    """Plivo's end-of-call webhook for outbound calls: record calls nobody answered."""
    settings: Settings = request.app.state.settings
    if not settings.plivo_enabled:
        return Response(status_code=503, content="Plivo is not configured")
    form = {k: str(v) for k, v in (await request.form()).items()}
    ok = verify_signature(
        "POST",
        public_url(settings, request.url.path, request.url.query),
        request.headers.get("x-plivo-signature-v3-nonce", ""),
        request.headers.get("x-plivo-signature-v3", ""),
        settings.plivo_auth_token,
        form,
    )
    if not ok:
        return Response(status_code=403, content="bad signature")
    job_id = request.query_params.get("job_id", "")
    status = UNANSWERED.get(form.get("CallStatus", "").lower())
    if job_id.isdigit() and status is not None:
        cause = form.get("HangupCauseName") or form.get("CallStatus", "")
        await run_db(
            request.app.state.session_factory, _mark_unanswered, int(job_id), status, cause
        )
    return Response(status_code=204)


def _mark_unanswered(session: Session, job_id: int, status: JobStatus, cause: str) -> None:
    job = outbound.get_job(session, job_id)
    if job.status == JobStatus.DIALLING:  # an answered call finishes through the agent instead
        outbound.set_job_status(session, job_id, status, f"Plivo: {cause}")


async def _close(ws: WebSocket, code: int) -> None:
    try:
        await ws.close(code=code)
    except Exception:  # peer already gone
        logger.debug("Could not close the Plivo socket")


@router.websocket("/ws/plivo/{secret}")
async def plivo_media(ws: WebSocket, secret: str) -> None:
    settings: Settings = ws.app.state.settings
    await ws.accept()
    if not settings.plivo_ws_secret or not secrets.compare_digest(
        secret.encode(), settings.plivo_ws_secret.encode()
    ):
        await _close(ws, CLOSE_UNAUTHORIZED)
        return

    try:
        first = json.loads(await asyncio.wait_for(ws.receive_text(), START_TIMEOUT_SECS))
        start = first["start"]
        stream_id, call_id = start["streamId"], start["callId"]
        if first.get("event") != "start":
            raise ValueError("first event was not start")
    except Exception:
        logger.warning("Plivo socket did not begin with a valid start event")
        await _close(ws, CLOSE_BAD_START)
        return

    provider = getattr(ws.app.state, "provider", None)
    if provider is None:
        logger.error("Plivo call arrived but no voice provider is configured")
        await _close(ws, CLOSE_UNAVAILABLE)
        return

    extra = pending_calls(ws.app).pop(str(call_id))
    if extra is not None:
        source = "answer webhook"
    else:
        extra = parse_extra_headers(first.get("extra_headers", start.get("extra_headers")))
        source = "start extra_headers" if extra else "none (treated as inbound, number unknown)"
    logger.info("Plivo call details from: {}", source)
    direction = "outbound" if extra.get("direction") == "outbound" else "inbound"
    job = extra.get("job_id", "")
    call = CallContext(
        call_id=str(call_id),
        direction=direction,
        caller_number=extra.get("customer") or None,
        outbound_job_id=int(job) if job.isdigit() else None,
        source="plivo",
    )
    serializer = PlivoFrameSerializer(
        stream_id=stream_id,
        call_id=call.call_id,
        auth_id=settings.plivo_auth_id,
        auth_token=settings.plivo_auth_token,
    )
    transport = FastAPIWebsocketTransport(
        ws,
        FastAPIWebsocketParams(
            audio_in_enabled=True, audio_out_enabled=True, serializer=serializer
        ),
    )
    resources = CallResources(
        settings=settings, session_factory=ws.app.state.session_factory, provider=provider
    )
    await run_call(call, transport, CallHandle(), resources)
