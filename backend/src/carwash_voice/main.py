"""FastAPI app factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from carwash_voice.api import health
from carwash_voice.config import Settings, get_settings
from carwash_voice.db.migrate import run_migrations
from carwash_voice.db.session import make_engine, make_session_factory
from carwash_voice.logging import setup_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        setup_logging(settings)
        engine = make_engine(settings.sqlalchemy_url)
        app.state.engine = engine
        app.state.session_factory = make_session_factory(engine)
        if settings.run_migrations_on_start:
            logger.info("Running database migrations")
            run_migrations(settings.sqlalchemy_url)
        logger.info("Started ({}) for {}", settings.app_env, settings.business_name)
        yield
        engine.dispose()

    app = FastAPI(title="Car wash voice agent", lifespan=lifespan)
    app.state.settings = settings
    app.include_router(health.router)
    return app


app = create_app()  # `uvicorn carwash_voice.main:app`; fails fast on bad config
