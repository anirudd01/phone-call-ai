"""loguru setup: readable locally, JSON lines elsewhere; call_id bound inside a call."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from contextlib import contextmanager

from loguru import logger

from carwash_voice.config import Settings


def setup_logging(settings: Settings) -> None:
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
