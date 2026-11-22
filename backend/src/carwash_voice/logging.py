"""loguru setup: readable locally, JSON lines elsewhere; call_id bound inside a call."""

from __future__ import annotations

import logging
import re
import sys
from collections.abc import Iterator
from contextlib import contextmanager

from loguru import logger

from carwash_voice.config import Settings

_PLIVO_WS_PATH = re.compile(r"/ws/plivo/[^\s\"?]+")


def _redact(text: str) -> str:
    return _PLIVO_WS_PATH.sub("/ws/plivo/***", text)


class RedactSecretPaths(logging.Filter):
    """Hide the secret path segment of the Plivo media socket in web-server log lines."""

    def filter(self, record: logging.LogRecord) -> bool:
        # Rewrite inside msg and args but keep the args tuple's shape: uvicorn's access
        # formatter unpacks exactly five args.
        if isinstance(record.msg, str):
            record.msg = _redact(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(_redact(a) if isinstance(a, str) else a for a in record.args)
        return True


def _redact_server_logs() -> None:
    for name in ("uvicorn.error", "uvicorn.access"):
        target = logging.getLogger(name)
        if not any(isinstance(f, RedactSecretPaths) for f in target.filters):
            target.addFilter(RedactSecretPaths())


def setup_logging(settings: Settings) -> None:
    _redact_server_logs()
    logger.remove()
    logger.configure(extra={"call_id": "-"})
    logger.add(
        sys.stderr,
        level=settings.log_level.upper(),
        serialize=not settings.is_dev,
        format="{time:HH:mm:ss.SSS} | {level:<7} | {extra[call_id]} | {message}\n{exception}",
    )


@contextmanager
def call_logging(call_id: str) -> Iterator[None]:
    """Bind call_id to every log line emitted inside the block."""
    with logger.contextualize(call_id=call_id):
        yield
