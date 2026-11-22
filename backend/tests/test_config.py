import pytest

from carwash_voice.config import ConfigError, Settings


def test_defaults_work_in_dev_without_secrets() -> None:
    s = Settings(_env_file=None)
    assert s.is_dev
    assert s.business_name == "Sparkle Car Wash"


def test_non_dev_requires_keys() -> None:
    with pytest.raises(ConfigError, match="ADMIN_API_KEY"):
        Settings(_env_file=None, app_env="prod")


def test_non_dev_ok_with_keys() -> None:
    s = Settings(_env_file=None, app_env="prod", admin_api_key="a", bridge_token="b")
    assert not s.is_dev


def test_openai_only_required_when_a_call_starts() -> None:
    s = Settings(_env_file=None)
    with pytest.raises(ConfigError, match="OPENAI_API_KEY"):
        s.require_openai()
    Settings(_env_file=None, openai_api_key="k", openai_realtime_model="m").require_openai()


@pytest.mark.parametrize("prefix", ["postgres://", "postgresql://"])
def test_postgres_url_gets_driver(prefix: str) -> None:
    s = Settings(_env_file=None, database_url=f"{prefix}u:p@host:5432/db")
    assert s.sqlalchemy_url == "postgresql+psycopg://u:p@host:5432/db"


def test_sqlite_url_unchanged() -> None:
    assert Settings(_env_file=None).sqlalchemy_url == "sqlite:///./data/dev.db"
