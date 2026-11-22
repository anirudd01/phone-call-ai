"""Engine and session factory."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker


def make_engine(url: str) -> Engine:
    parsed = make_url(url)
    is_sqlite = parsed.get_backend_name() == "sqlite"
    kwargs: dict[str, Any] = {"pool_pre_ping": True}
    if is_sqlite:
        if parsed.database and parsed.database != ":memory:":
            Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)
        # DB work runs in worker threads so audio never stalls on the event loop.
        kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_engine(url, **kwargs)
    if is_sqlite:

        @event.listens_for(engine, "connect")
        def _enable_foreign_keys(dbapi_conn: Any, _record: Any) -> None:
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

    return engine


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)


async def run_db[T](
    factory: sessionmaker[Session], fn: Callable[..., T], *args: Any, **kwargs: Any
) -> T:
    """Run a blocking DB function in a worker thread with its own session.

    Keeps database work off the event loop so call audio never stalls.
    """

    def work() -> T:
        with factory() as session:
            return fn(session, *args, **kwargs)

    return await asyncio.to_thread(work)
