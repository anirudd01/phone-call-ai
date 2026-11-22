from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from carwash_voice.cli import main as cli_main
from carwash_voice.domain import calls
from carwash_voice.voice.recording import LocalRecordingStore, wav_bytes
from carwash_voice.voice.session import CallHandle


def test_wav_bytes_has_header_and_format() -> None:
    data = wav_bytes(bytes(16), 16000, 2)
    assert data[:4] == b"RIFF" and data[8:12] == b"WAVE"


def test_store_saves_under_year_month_and_reads_back(tmp_path: Path) -> None:
    store = LocalRecordingStore(tmp_path)
    when = datetime(2026, 3, 5, tzinfo=UTC)
    rel = store.save("abc-123", b"audio", when)
    assert rel == "2026/03/abc-123.wav"
    with store.open(rel) as f:
        assert f.read() == b"audio"
    assert store.delete(rel) is True
    assert store.delete(rel) is False


@pytest.mark.parametrize("bad", ["../evil", "a/b", "", "x" * 200, ".."])
def test_store_rejects_unsafe_call_ids(tmp_path: Path, bad: str) -> None:
    with pytest.raises(ValueError):
        LocalRecordingStore(tmp_path).save(bad, b"x")


def test_store_blocks_path_escape(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        LocalRecordingStore(tmp_path).open("../outside.wav")


def test_handle_transcript_ignores_blank_text() -> None:
    h = CallHandle()
    h.add_transcript("agent", "  ")
    h.add_transcript("caller", " hi ", "2026-01-01T00:00:00Z")
    assert h.transcript == [{"role": "caller", "text": "hi", "at": "2026-01-01T00:00:00Z"}]


def test_purge_removes_old_audio_and_keeps_transcript(session: Session, tmp_path: Path) -> None:
    store = LocalRecordingStore(tmp_path)
    for cid, age in (("old-call", 100), ("new-call", 1)):
        calls.create_call(session, cid, "inbound")
        c = calls.finalize_call(
            session,
            cid,
            "completed",
            transcript=[{"role": "caller", "text": "hi", "at": "t"}],
            audio_path=store.save(cid, b"x"),
        )
        c.ended_at = datetime.now(UTC) - timedelta(days=age)
        session.commit()
    assert calls.purge_recordings(session, 90, store.delete) == 1
    assert calls.get_call(session, "old-call").audio_path is None
    assert calls.get_call(session, "old-call").transcript
    assert calls.get_call(session, "new-call").audio_path is not None
    assert [p.name for p in tmp_path.rglob("*.wav")] == ["new-call.wav"]


def test_cli_purge_runs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'cli.db').as_posix()}")
    monkeypatch.setenv("RECORDINGS_DIR", str(tmp_path / "rec"))
    monkeypatch.chdir(tmp_path)
    from carwash_voice.config import get_settings
    from carwash_voice.db.migrate import run_migrations

    get_settings.cache_clear()
    try:
        run_migrations(get_settings().sqlalchemy_url)
        assert cli_main(["purge-recordings"]) == 0
        assert "Removed audio for 0 call(s)" in capsys.readouterr().out
    finally:
        get_settings.cache_clear()
