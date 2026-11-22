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

Already set up on this laptop: `backend/.env` has the keys, and `local/bridge/.env` was created
with the same bridge token and `IN_DEVICE=Plantronics`, `OUT_DEVICE=Plantronics`. Wear the
headset (otherwise the agent hears itself), then use two PowerShell windows.

If `uv` is not found, put `py -3.12 -m` in front of every `uv` below.

Window 1, the server (leave it running):

    cd backend
    uv run uvicorn carwash_voice.main:app

Window 2, the bridge:

    cd localridge
    uv run carwash-bridge run

At the `>` prompt type `a` and press Enter, press Enter again to skip the caller number, and
talk. The agent speaks first. Type `e` to end the call and `q` to quit.

Afterwards, see the call at http://localhost:8000/docs (click Authorize, paste `ADMIN_API_KEY`
from `backend/.env`): `GET /api/calls` shows the transcript and the saved audio file.

### Setting up on another laptop
1. `cd localridge`, copy `.env.example` to `.env`.
2. Set `BRIDGE_TOKEN` to the same value as `BRIDGE_TOKEN` in `backend/.env`.
3. Run `uv run carwash-bridge devices`. It lists every device. Put a distinctive part of your
   headset's name in `IN_DEVICE` and `OUT_DEVICE` (for example `Plantronics`), or leave both
   empty to use the laptop's default microphone and speakers.
