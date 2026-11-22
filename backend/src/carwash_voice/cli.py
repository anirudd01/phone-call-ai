"""Command-line tools: uv run carwash-voice <command>."""

from __future__ import annotations

import argparse

from carwash_voice.config import get_settings
from carwash_voice.db.session import make_engine, make_session_factory
from carwash_voice.domain import calls
from carwash_voice.voice.recording import LocalRecordingStore


def purge_recordings_command() -> int:
    settings = get_settings()
    factory = make_session_factory(make_engine(settings.sqlalchemy_url))
    store = LocalRecordingStore(settings.recordings_dir)
    with factory() as session:
        count = calls.purge_recordings(session, settings.recording_retention_days, store.delete)
    print(
        f"Removed audio for {count} call(s) older than "
        f"{settings.recording_retention_days} days (transcripts kept)."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="carwash-voice")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("purge-recordings", help="delete call audio older than the retention period")
    args = parser.parse_args(argv)
    if args.command == "purge-recordings":
        return purge_recordings_command()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
