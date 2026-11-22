"""FastAPI app factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from carwash_voice.api import admin, health
from carwash_voice.config import Settings, get_settings
from carwash_voice.db.migrate import run_migrations
from carwash_voice.db.session import make_engine, make_session_factory
from carwash_voice.logging import setup_logging
from carwash_voice.transports.plivo.dialer import Dialer, PlivoDialer
from carwash_voice.transports.plivo.endpoint import router as plivo_router
from carwash_voice.voice.providers.base import VoiceProvider
from carwash_voice.voice.providers.openai_realtime import OpenAIRealtimeProvider


def create_app(
    settings: Settings | None = None,
    provider: VoiceProvider | None = None,
    dialer: Dialer | None = None,
) -> FastAPI:
    """Build the app. `provider` is the AI provider and `dialer` places outbound calls.

    Tests pass fakes for both.
    """
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        setup_logging(settings)
        engine = make_engine(settings.sqlalchemy_url)
        app.state.engine = engine
        app.state.session_factory = make_session_factory(engine)
        if app.state.provider is None and settings.openai_api_key:
            app.state.provider = OpenAIRealtimeProvider(settings, app.state.session_factory)
        if settings.run_migrations_on_start:
            logger.info("Running database migrations")
            run_migrations(settings.sqlalchemy_url)
        logger.info("Started ({}) for {}", settings.app_env, settings.business_name)
        yield
        engine.dispose()

    app = FastAPI(title="Car wash voice agent", lifespan=lifespan)
    app.state.settings = settings
    app.state.provider = provider
    app.state.dialer = dialer or PlivoDialer(settings)
    app.include_router(health.router)
    app.include_router(admin.router)
    app.include_router(admin.bridge_router)
    app.include_router(plivo_router)
    if settings.enable_local_bridge:
        from carwash_voice.transports.local.endpoint import router as local_router

        app.include_router(local_router)
    return app


app = create_app()  # `uvicorn carwash_voice.main:app`; fails fast on bad config
