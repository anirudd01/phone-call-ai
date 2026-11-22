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
