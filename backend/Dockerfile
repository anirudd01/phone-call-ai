# Backend image for Railway (build context = the backend/ folder).
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS build
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
# Dependencies first so this layer is cached until the lock file changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
COPY alembic.ini ./
RUN uv sync --frozen --no-dev

FROM python:3.12-slim-bookworm
RUN useradd --create-home --uid 1000 app
WORKDIR /app
COPY --from=build --chown=app:app /app /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    RECORDINGS_DIR=/data/recordings
RUN mkdir -p /data/recordings && chown -R app:app /data
USER app
EXPOSE 8000
# Railway sets $PORT. Migrations run when the app starts (RUN_MIGRATIONS_ON_START).
CMD ["sh", "-c", "exec uvicorn carwash_voice.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
