# Running locally (Windows)

Stub; completed in task 8. Commands verified so far (PowerShell, from a project folder):

```powershell
py -3.12 -m pip install --user uv     # if uv is missing; then use "py -3.12 -m uv" or add Scripts to PATH
uv sync                               # install dependencies
uv run ruff check                     # lint
uv run ruff format --check            # format check
uv run pytest                         # tests
```

Projects: `backend/`, `local/bridge/`, `local/spike/` (each has its own `pyproject.toml`).

## Talk to the agent with a headset (laptop mode)

Use a headset so the agent does not hear itself. Two PowerShell windows.

1. Backend: in `backend/`, make sure `.env` has `OPENAI_API_KEY`, `OPENAI_REALTIME_MODEL` and
   `BRIDGE_TOKEN`, then run `uv run uvicorn carwash_voice.main:app`.
2. Bridge: in `local/bridge/`, copy `.env.example` to `.env`, set `BRIDGE_TOKEN` to the same
   value as the backend, and set `IN_DEVICE` and `OUT_DEVICE` to part of your headset name
   (run `uv run carwash-bridge devices` to see names), or leave them empty for the defaults.
   Then run `uv run carwash-bridge run`.
3. At the `>` prompt press `a` then Enter, skip the caller number, and talk. `e` ends the
   call and `q` quits. Afterwards check the ticket at `http://localhost:8000/docs`
   (use the `X-Admin-Key` header). The call's audio is under `backend/data/recordings/`.
