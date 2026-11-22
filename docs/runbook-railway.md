# Deploying the backend to Railway

Status: files written, **not yet deployed**. The Dockerfile has not been built (no Docker on the
work laptop); the app itself was started in production mode locally and answered `/healthz`.
Railway prices and region names change, so check them in the Railway dashboard before paying.

## One-time setup (you, in the Railway website)

1. Create a project and choose "Deploy from GitHub repo", pick `anirudd01/phone-call-ai`.
2. Open the service settings and set **Root Directory** to `backend`. Railway then finds
   `backend/Dockerfile` and `backend/railway.toml` (health check `/healthz`).
3. In the project add a **Postgres** database ("New" then "Database" then "PostgreSQL").
4. On the backend service add a **Volume** mounted at `/data` (recordings live there; the
   container's own disk is wiped on each deploy).
5. In the service settings choose a region near India if one is offered (Singapore is the
   closest Railway has offered; confirm in the dashboard).
6. In **Variables** add the names below (values: you type them; never put them in git):

| Variable | Value |
|---|---|
| `APP_ENV` | `production` |
| `DATABASE_URL` | reference the Postgres variable `${{Postgres.DATABASE_URL}}` |
| `OPENAI_API_KEY` | your key |
| `OPENAI_REALTIME_MODEL` | `gpt-realtime-2.1` |
| `OPENAI_REALTIME_VOICE` | `marin` |
| `ADMIN_API_KEY` | a new long random string |
| `BRIDGE_TOKEN` | a new long random string |
| `ENABLE_LOCAL_BRIDGE` | `true` while testing with the headset, then `false` |
| `RECORDINGS_DIR` | `/data/recordings` |
| `PUBLIC_BASE_URL` | the service's public URL, for example `https://xxx.up.railway.app` (generate a domain under Settings, Networking) |
| `PLIVO_AUTH_ID`, `PLIVO_AUTH_TOKEN`, `PLIVO_WS_SECRET`, `PLIVO_NUMBER` | from Plivo, see `docs/plivo-setup.md` |

Optional: `BUSINESS_NAME`, `AGENT_NAME`, `MAX_CALL_SECONDS`, `RECORDING_RETENTION_DAYS`.
If the app cannot write to `/data` (permission error in the logs), add the variable
`RAILWAY_RUN_UID` = `0`.

## Check it works

- Open `https://<your-domain>/healthz`: it should show `{"status":"ok","database":"ok"}`.
- Headset test against Railway: in `local/bridge/.env` set
  `BACKEND_WS_URL=wss://<your-domain>/ws/local-bridge`,
  `BACKEND_HTTP_URL=https://<your-domain>` and `BRIDGE_TOKEN` to the Railway value, then run
  `uv run carwash-bridge run` as in `docs/runbook-local.md`.

## Day to day

- Logs: the service's Deployments tab. Every call's lines carry its call id.
- Roll back: Deployments tab, pick an older deployment, Redeploy.
- Old recordings: run `carwash-voice purge-recordings` in the service's shell (Railway CLI
  `railway ssh`) or add a Railway cron service later. Nothing deletes them automatically yet.
- Calls are tied to the running process: a redeploy ends calls in progress.
