"""FastAPI dependencies: DB session and the two kinds of authentication."""

from __future__ import annotations

import secrets
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from carwash_voice.config import Settings


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings_dep)]


def _check(expected: str, supplied: str | None, what: str) -> None:
    if not expected:
        raise HTTPException(status_code=503, detail=f"{what} is not configured on the server")
    if not supplied or not secrets.compare_digest(supplied.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="Invalid credentials")


def require_admin(
    settings: SettingsDep, x_admin_key: Annotated[str | None, Header()] = None
) -> None:
    _check(settings.admin_api_key, x_admin_key, "ADMIN_API_KEY")


def require_bridge(
    settings: SettingsDep, authorization: Annotated[str | None, Header()] = None
) -> None:
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    _check(settings.bridge_token, token, "BRIDGE_TOKEN")
