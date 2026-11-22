"""Application settings, read from environment variables (and a local .env file)."""

from __future__ import annotations

from functools import lru_cache
from typing import Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigError(RuntimeError):
    """Raised when a required setting is missing."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "dev"
    log_level: str = "INFO"
    database_url: str = "sqlite:///./data/dev.db"
    run_migrations_on_start: bool = True

    openai_api_key: str = ""
    openai_realtime_model: str = ""
    openai_realtime_voice: str = ""

    bridge_token: str = ""
    admin_api_key: str = ""
    enable_local_bridge: bool = True

    # Public https URL of this server (Railway). Plivo calls back to it.
    public_base_url: str = ""
    plivo_auth_id: str = ""
    plivo_auth_token: str = ""
    plivo_ws_secret: str = ""  # secret path segment of the media WebSocket URL
    plivo_number: str = ""  # our Plivo number, used as the caller ID for outbound calls

    business_name: str = "Sparkle Car Wash"
    agent_name: str = "Asha"
    default_language: str = "en-IN"
    agent_languages: str = "Indian English, Kannada, Hindi, Hinglish (mixed Hindi and English)"

    recordings_dir: str = "./data/recordings"
    recording_retention_days: int = 90
    max_call_seconds: int = 900
    port: int = 8000

    @property
    def is_dev(self) -> bool:
        return self.app_env == "dev"

    @property
    def plivo_enabled(self) -> bool:
        return all(
            (self.public_base_url, self.plivo_auth_id, self.plivo_auth_token, self.plivo_ws_secret)
        )

    @property
    def sqlalchemy_url(self) -> str:
        """Database URL with the psycopg driver (Railway gives a plain postgresql:// URL)."""
        url = self.database_url
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return "postgresql+psycopg://" + url[len(prefix) :]
        return url

    @model_validator(mode="after")
    def _require_secrets_outside_dev(self) -> Self:
        if not self.is_dev:
            missing = [
                name.upper()
                for name in ("admin_api_key", "bridge_token")
                if not getattr(self, name)
            ]
            if missing:
                raise ConfigError(
                    f"Missing required settings for APP_ENV={self.app_env}: {', '.join(missing)}"
                )
        return self

    def require_openai(self) -> None:
        """Called when a call starts; the API and tests run without these."""
        missing = [
            name.upper()
            for name in ("openai_api_key", "openai_realtime_model")
            if not getattr(self, name)
        ]
        if missing:
            raise ConfigError(f"Missing required settings to run a call: {', '.join(missing)}")


@lru_cache
def get_settings() -> Settings:
    return Settings()
