"""/ws/local-bridge: auth, wait for `start`, then hand over to the call session.

LOCAL TESTING ONLY. Only registered when ENABLE_LOCAL_BRIDGE is true.
"""

from __future__ import annotations

import asyncio
import json
import secrets
from typing import Any

from fastapi import APIRouter, WebSocket
from loguru import logger
from pipecat.frames.frames import OutputTransportMessageFrame, OutputTransportMessageUrgentFrame
from pipecat.transports.websocket.fastapi import FastAPIWebsocketParams, FastAPIWebsocketTransport

from carwash_voice.transports.local import protocol
from carwash_voice.transports.local.serializer import LocalBridgeFrameSerializer
from carwash_voice.voice.session import CallContext, CallHandle, CallResources, run_call

router = APIRouter()


def _authorized(ws: WebSocket, token: str) -> bool:
    header = ws.headers.get("authorization", "")
    if not token or not header.lower().startswith("bearer "):
        return False
    return secrets.compare_digest(header[7:].strip().encode(), token.encode())


async def _reject(ws: WebSocket, code: int, message: str) -> None:
    try:
        await ws.send_text(json.dumps(protocol.error(message)))
        await ws.close(code=code)
    except Exception:  # peer already gone
        logger.debug("Could not send rejection to bridge")


@router.websocket("/ws/local-bridge")
async def local_bridge(ws: WebSocket) -> None:
    settings = ws.app.state.settings
    await ws.accept()  # accept first so the close code reaches the client

    if not _authorized(ws, settings.bridge_token):
        await ws.close(code=protocol.CLOSE_UNAUTHORIZED)
        return

    try:
        first = await asyncio.wait_for(ws.receive_text(), protocol.START_TIMEOUT_SECS)
        start = protocol.parse_start(first)
    except TimeoutError:
        await _reject(ws, protocol.CLOSE_BAD_START, "timed out waiting for start")
        return
    except ValueError as exc:
        await _reject(ws, protocol.CLOSE_BAD_START, str(exc))
        return
    except Exception:  # disconnected or sent binary before start
        await _reject(ws, protocol.CLOSE_BAD_START, "expected a text 'start' message")
        return

    provider = getattr(ws.app.state, "provider", None)
    if provider is None:
        await _reject(ws, protocol.CLOSE_UNAVAILABLE, "voice provider is not configured")
        return

    handle = CallHandle(
        end_notice=lambda reason: OutputTransportMessageFrame(message=protocol.end_call(reason))
    )

    def on_control(message: dict[str, Any]) -> None:
        kind = message.get("type")
        if kind == "stop":
            reason = str(message.get("reason", "operator_hangup"))
            asyncio.get_running_loop().create_task(handle.end(reason))
        elif kind == "mark":
            logger.info("Bridge mark: {}", message.get("name"))

    transport = FastAPIWebsocketTransport(
        ws,
        FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            audio_out_10ms_chunks=2,  # 20 ms frames on the wire
            serializer=LocalBridgeFrameSerializer(on_control),
        ),
    )
    call = CallContext(
        call_id=start.call_id,
        direction=start.direction,
        caller_number=start.caller_number,
        outbound_job_id=start.outbound_job_id,
        source=f"local-bridge:{start.bridge_id}",
    )
    resources = CallResources(
        settings=settings, session_factory=ws.app.state.session_factory, provider=provider
    )
    await run_call(
        call,
        transport,
        handle,
        resources,
        on_ready=lambda: OutputTransportMessageUrgentFrame(message=protocol.ready(call.call_id)),
    )
