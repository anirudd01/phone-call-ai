"""Place outbound calls through Plivo's REST API.

Plivo dials the customer, and when they answer it asks our /plivo/answer URL what to do, which
returns the same <Stream> XML as for inbound calls.
"""

from __future__ import annotations

from typing import Protocol
from urllib.parse import urlencode

import httpx
from loguru import logger

from carwash_voice.config import Settings

API = "https://api.plivo.com/v1/Account/{auth_id}/Call/"
RING_TIMEOUT_SECS = 40


class DialError(RuntimeError):
    """Plivo refused or could not be reached; the message is safe to show to the operator."""


class Dialer(Protocol):
    async def dial(self, job_id: int, to_number: str) -> str:
        """Start the call and return Plivo's request id."""
        ...


class PlivoDialer:
    def __init__(self, settings: Settings) -> None:
        self._s = settings

    async def dial(self, job_id: int, to_number: str) -> str:
        s = self._s
        if not (s.plivo_enabled and s.plivo_number):
            raise DialError("Plivo is not configured (PUBLIC_BASE_URL, PLIVO_* and PLIVO_NUMBER)")
        base = s.public_base_url.rstrip("/")
        query = urlencode({"job_id": job_id})
        body = {
            "from": s.plivo_number.lstrip("+"),
            "to": to_number.lstrip("+"),
            "answer_url": f"{base}/plivo/answer?{query}",
            "answer_method": "POST",
            "hangup_url": f"{base}/plivo/hangup?{query}",
            "hangup_method": "POST",
            "ring_timeout": RING_TIMEOUT_SECS,
            "time_limit": s.max_call_seconds,
        }
        try:
            async with httpx.AsyncClient(timeout=15) as http:
                r = await http.post(
                    API.format(auth_id=s.plivo_auth_id),
                    json=body,
                    auth=(s.plivo_auth_id, s.plivo_auth_token),
                )
        except httpx.HTTPError as exc:
            raise DialError(f"Could not reach Plivo: {type(exc).__name__}") from exc
        if r.status_code not in (200, 201, 202):
            logger.error("Plivo refused the call: {} {}", r.status_code, r.text[:300])
            raise DialError(f"Plivo refused the call (HTTP {r.status_code}): {r.text[:200]}")
        request_uuid = str(r.json().get("request_uuid", ""))
        logger.info("Plivo accepted outbound job {} (request {})", job_id, request_uuid)
        return request_uuid
