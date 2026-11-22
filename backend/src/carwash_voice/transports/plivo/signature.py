"""Check Plivo's V3 request signature using Plivo's own SDK implementation."""

from __future__ import annotations

from plivo.utils.signature_v3 import validate_v3_signature


def verify_signature(
    method: str,
    url: str,
    nonce: str,
    signature: str,
    auth_token: str,
    params: dict[str, str] | None = None,
) -> bool:
    """True only when the signature matches; any problem (missing headers, bad input) is False."""
    if not (nonce and signature and auth_token):
        return False
    try:
        return bool(
            validate_v3_signature(method, url, nonce, auth_token, signature, dict(params or {}))
        )
    except Exception:
        return False
