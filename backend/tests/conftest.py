from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from carwash_voice.config import Settings
from carwash_voice.main import create_app


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        recordings_dir=str(tmp_path / "rec"),
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as c:
        yield c
