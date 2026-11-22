"""Health endpoint: status and database connectivity."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response
from loguru import logger
from sqlalchemy import text

router = APIRouter()


@router.get("/healthz")
def healthz(request: Request, response: Response) -> dict[str, str]:
    try:
        with request.app.state.engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Health check: database unreachable")
        response.status_code = 503
        return {"status": "error", "database": "down"}
    return {"status": "ok", "database": "ok"}
