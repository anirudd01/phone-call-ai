# TASKS: implementation brief and tracker

This file is both the **input prompt** for the coding agent (Claude Sonnet 5.5) and the
**live tracker**. Read [README.md](README.md) first for the why. Then work through the
tasks below in order, updating this file as you go.

---

## 0. Current state: read this first after a context reset

**Opus review 2026-11-22: read section 8 first.** Opus fixed the code findings (R1 to R7); the
open items for you are R8 to R12 there. Tests are now 122 (backend) plus 12 (bridge).

**Plivo account: pending on the user.** Plivo sign-up needs a work email; the user is setting up
email on their domain `shyn.co.in` first. Until then nothing can be tried against real Plivo.

**Last updated:** 2026-11-22 (paused by the user). Done: tasks 1 to 7. Coded and tested offline only: Plivo inbound transport, Plivo outbound dialling (task 9), Railway files (task 11). Parked: task 0 (Bluetooth). **Provider decided: Plivo** (the business has a Udyam registration). **Git: commit and push straight to `main`, no branches** (user rule until a server is running). Research: `docs/research-cpaas-exotel-vs-plivo.md`. Plivo guide: `docs/plivo-setup.md`. Railway guide: `docs/runbook-railway.md`.

**Direction change:** the phone path is now a **CPaaS** (Exotel or Plivo), not the Bluetooth
bridge. Task 0 is parked after two failed attempts on the spare laptop (the phone keeps
dropping the link; the Windows driver error `0x48F` / `GLE 0x1` appears when opening the
phone's `Hands-Free HF Audio` device). `local/` stays only as phone-free laptop-mic test tooling.
**Decided 2026-11-22: Plivo.** (Old note, now resolved:) Not researched yet. The user said they will
decide; offer a web-researched comparison (India pricing, number KYC, bidirectional media
streaming, per-minute cost) when it is needed. Pipecat already ships `ExotelFrameSerializer`
and `PlivoFrameSerializer` (8 kHz default). A new transport only needs to build a Pipecat
transport and call `voice/session.py: run_call()`; `voice/` must not change.

**Git state (verify with `git status` and `git log`):** one branch, `main`, in sync with GitHub
(`anirudd01/phone-call-ai`) at the time of the pause. Pushing is allowed and expected after each
commit. Never commit `backend/.env` or `local/bridge/.env` (both git-ignored; real keys).

**What works (all verified):**
- Backend in `backend/` (Python 3.12, FastAPI, Pipecat 1.16.0, SQLAlchemy 2, Alembic). 122 offline
  tests (backend) plus 12 (bridge), Ruff clean. Run tests: `cd backend; py -3.12 -m uv run pytest -q`. Lint:
  `py -3.12 -m uv run ruff check; py -3.12 -m uv run ruff format --check`.
- Live test (spends a little money): `py -3.12 -m uv run pytest -m live -s`. Passed 3 of 3: the
  agent greets, takes a spoken English complaint (fixtures in `backend/tests/fixtures/`) and
  creates a ticket. Model `gpt-realtime-2.1`, voice `marin`, set in `backend/.env`.
- Server: `py -3.12 -m uv run uvicorn carwash_voice.main:app`; `/healthz`, `/docs`, admin API
  (`X-Admin-Key`), bridge endpoints (bearer token), `/ws/local-bridge` (protocol in
  `local/docs/bridge-protocol.md`). The real provider is wired automatically when
  `OPENAI_API_KEY` is set.

**Verified live:** headset test on this laptop through `local/bridge` (laptop mode, Plantronics
headset, `IN_DEVICE`/`OUT_DEVICE`=`Plantronics`, both set in `local/bridge/.env`): the agent greets,
the call is recorded as stereo WAV with a transcript, and the call row is finalised. The user said
"testing complete" without detailed feedback on echo, delay or quality (ask if it matters).

**Not yet verified (do not claim these work):** anything against real Plivo (inbound, outbound,
signature check, `start.extra_headers`, audio content type, hang-up cutting off the goodbye);
the `end_call` goodbye flow live; outbound calls live; Kannada, Hindi, Hinglish; latency;
Postgres (only SQLite so far); the Docker build (no Docker on the work laptop); Railway deploy
and volume permissions; a live transcript from a real OpenAI call beyond the greeting.

**Environment gotchas (this work laptop, Windows):**
- `uv` is not on PATH: use `py -3.12 -m uv ...`. Set `PYTHONUTF8=1`.
- Pipecat 1.16.0 needs `loguru<0.8` (pinned). Use `PipelineWorker` and `WorkerRunner`
  (`add_workers()` then `run()`); `PipelineTask`/`PipelineRunner` are deprecated.
- The Bash tool turns backslash escapes in commands into real characters (a `\x00` became a NUL
  byte in a file, and some heredocs fail). Create files with the Write tool; if a script needs a
  backslash, build it with `chr(92)` or `bytes([92])`.
- Starlette test client: `ws.receive()` returns a close as a `websocket.close` message.
  In Pipecat tests, system frames overtake queued ones; put a `SleepFrame` between them.
- Long commands (live tests, about 55 s each) should run in the background.
- The `.env` also contains unused keys from another project (`ACTIVE_MODEL`, `TTS_SPEED`,
  `PYTHONDONTWRITEBYTECODE`); settings ignore them.

**Suggested next steps:** (1) the user creates the Railway project, Postgres and volume and
sets variables per `docs/runbook-railway.md` (paid resources: the user decides), then gives the
public URL; (2) rerun the headset test against Railway (`BACKEND_WS_URL=wss://<domain>/ws/local-bridge`)
= Task 11 acceptance; (3) the user does Plivo KYC with the Udyam certificate, rents a
landline-series number, asks Plivo whether voice service calls need DLT registration, and sets
the `PLIVO_*` variables; (4) first real inbound call, then one outbound (`POST
/api/outbound-jobs/{id}/dial`), fix whatever the "not yet verified" list gets wrong; (5) Task 10
language scripts in `docs/language-test.md` (the user judges by listening); (6) try the Docker
build on the spare laptop; (7) Task 13 hand-off pack. Optional: a cron to run
`carwash-voice purge-recordings`; a calling-hours guard for outbound calls.

---

## 1. Your role and how to work

You are implementing a phone-call voice agent for a car-wash business in India. The
planning (by Opus) and the user's decisions are final and recorded in section 3; do not
re-open them. If something in this plan turns out to be wrong in practice (an API
changed, a library class doesn't exist), stop, record what you found in section 6
("Verified facts / surprises"), and ask the user before changing direction.

Working rules:

1. **One task at a time.** Set its status to `IN PROGRESS`, do it, verify it against its
   acceptance criteria, then set `DONE` and fill in the "Result" line. Use `BLOCKED` with
   a reason when you need the user (for example, a hardware step).
2. **Never guess library APIs.** Pipecat and the OpenAI Realtime API change often. Pin
   versions in `pyproject.toml` and check class names, constructor arguments and frame
   types against the installed package source or its official docs before writing code.
   Record the exact versions and class names you used in section 6.
3. **Windows first, two machines.** Both laptops run Windows 11 (PowerShell 5.1 and Git
   Bash) and both have Bluetooth.
   - **Work laptop:** where you write code, run unit tests and the "laptop mic" mode.
     **No admin rights**, company policies, sometimes a VPN. No phone pairing here.
   - **Spare laptop:** the user's own machine, **with admin rights and Docker**. It sits
     near the phone and runs the Bluetooth bridge and all real phone tests. The user has
     to switch it on, so the status board's "Where" column says when it is needed; tell
     the user ahead of time.
   Code reaches the spare laptop through the GitHub repo (clone/pull there). Every
   command in docs must work on Windows.
4. **Use `uv`** for Python environments and dependencies (user-level install, no admin).
   Python 3.12. Each of `backend/` and `local/bridge/` is its own project with its own
   `pyproject.toml` and lock file.
5. **Lint and test before calling anything done:** `ruff check`, `ruff format --check`
   and `pytest` must pass in each project you touched. Configure Ruff in `pyproject.toml`
   (line length 100, rules `E,F,W,I,UP,B,SIM,ASYNC`). Type hints everywhere.
6. **Secrets:** never commit `.env`, keys or tokens. Provide `.env.example` with key names
   and safe placeholder values only. Never print secret values in logs or docs.
7. **Git:** the user set up git and the GitHub repo. **Current rule (user, 2026-11-22):
   commit and push straight to `main`, no branches**, until a server is running; then the
   user may switch to `develop` + `feature/<short-name>`. Never use a `chore/` branch. Write
   commit messages to a file and use `git commit -F <file>`. Stage files by name (no
   `git add -A` / `git add .`).
8. **Keep it simple.** Prototype quality with production habits: clear structure,
   config via env vars, structured logs, tests for logic. No speculative abstractions
   beyond those named in this plan (the transport and AI-provider seams are deliberate).
9. **Keep this file current.** Tick boxes, fill "Result" lines, add decisions and
   surprises. The user listens to summaries via text-to-speech, so when you report back,
   write plain full sentences.

---

## 2. Status board

| # | Task | Status | Where | Needs user? |
|---|---|---|---|---|
| 0 | Bluetooth bridge feasibility test (scripts + user run) | PARKED (user chose CPaaS on 2026-11-22; phone kept dropping the Bluetooth link; may retry later) | Work (write) → **Spare** (run) | Yes (hardware) |
| 1 | Repo scaffolding and tooling (user has set up git) | DONE (single branch `main`) | Work | Approve commit |
| 2 | Backend skeleton: config, logging, health, DB models, migrations | DONE | Work | No |
| 3 | Ticket/customer domain + admin REST API | DONE | Work | No |
| 4 | Local-bridge WebSocket protocol + serializer + call session lifecycle | DONE | Work | No |
| 5 | Voice agent: OpenAI Realtime pipeline, persona, tools | DONE | Work | API key |
| 6 | Recording: audio + transcript storage | DONE | Work | No |
| 7 | Bridge app in `local/` (Windows): laptop-mic mode first; Bluetooth device mode parked | DONE (headset-tested) | Work | No |
| 8 | Local end-to-end: laptop-mic mode (phone via Bluetooth parked) | MOSTLY DONE (user headset test; ticket flow and detailed notes not recorded) | Work, then **Spare** | Yes (testing) |
| 9 | Outbound update calls via the Plivo API | CODE DONE (untested on real Plivo) | **Spare** | Yes (testing) |
| 10 | Language check: English, Kannada, Hindi, Hinglish | TODO | Work (laptop mic) or **Spare** | Yes (listening) |
| 11 | Railway deployment (Dockerfile, Postgres, volume) | FILES DONE, deploy pending (user) | Work (Docker test on **Spare**) | Yes (Railway account) |
| 12 | Railway ↔ phone end-to-end (re-scope: via CPaaS number) | TODO | **Spare** | Yes (testing) |
| 13 | Hand-off pack for Opus review | TODO | Work | No |
| — | Phase 1c (Android app) | PARKED | — | — |

---

## 3. Fixed decisions (from the user, 2026-11-22)

| Topic | Decision |
|---|---|
| Country / users | India. Customers call an Indian mobile SIM (SIM 2 of the user's Android phone). |
| Phone → backend | **Superseded 2026-11-22: Plivo (see section 7).** Original decision: Bluetooth hands-free bridge on the **spare Windows laptop**, using Windows' own Bluetooth hands-free audio devices. **No Windows Phone Link app**, ever. Run the bridge as plain Windows Python, not in Docker or WSL (containers can't reach the laptop's Bluetooth). If task 0 fails, stop and ask the user (see task 0). |
| Purpose of the bridge | **Local testing only**: to see that the phone flow works and get a feel for the agent. The real, long-term phone path is a CPaaS (phase 2). |
| Code layout | Everything specific to the Bluetooth bridge lives in a top-level **`local/`** folder (bridge app, spike scripts, its docs), plus the backend's adapter for it in `backend/src/carwash_voice/transports/local/`. Nothing outside these two places may import from them, so they can be deleted later without touching the rest. The real call path (CPaaS transports, agent, tools, data) goes in the normal backend structure. |
| Machines | Work laptop: coding, unit tests, laptop-mic mode. Spare laptop (admin + Docker): Bluetooth bridge and all phone tests; can also run the backend natively or in Docker. |
| Git | The user sets up git and the GitHub repo. |
| Call answering / dialling | **Manual in phase 1.** The user taps Answer or dials on the phone itself. The bridge operator console tells the backend when a call starts and ends. |
| AI voice | **OpenAI Realtime speech-to-speech** through Pipecat, behind a provider seam so Gemini Live or an STT→LLM→TTS cascade can be swapped in. |
| Backend stack | Python 3.12, FastAPI, Pipecat, SQLAlchemy 2 + Alembic, pydantic-settings. |
| Languages | Primary **English (Indian)** and **Kannada**; also Hindi and Hinglish. Tamil, Telugu, Marathi later. The agent answers in the language the customer uses. |
| Scope | Inbound complaint → ticket; ticket status lookup; outbound update calls; human handoff request (ticket flagged *callback requested*). |
| Tickets | Built in this repo: SQLite locally, Postgres on Railway. |
| Customer identity | No customer list yet. Use caller number when known, ask name, car registration, wash location and date; upsert a customer record. |
| Storage per call | **Audio + transcript + ticket.** Agent announces recording at the start of each call. |
| Persona | Config placeholders: `BUSINESS_NAME="Sparkle Car Wash"`, `AGENT_NAME="Asha"`. |
| Hosting path | Laptop → Railway (pick an Asia region, e.g. Singapore, if available) → Railway + CPaaS; VPS if Railway is unsuitable. |
| Out of scope now | Call summaries for human agents, notifications, Android companion app. (CPaaS moved into scope on 2026-11-22: Plivo.) |

---

## 4. Target architecture (build to this)

### 4.1 Components

```
local/bridge (Windows, spare laptop)               backend (FastAPI + Pipecat)
────────────────────────────────────               ───────────────────────────
audio in  (BT hands-free mic = caller voice) ──►   /ws/local-bridge (one WebSocket per call)
audio out (BT hands-free speaker = to caller) ◄──    └─ transports/local: serializer
operator console (keys: answer/outbound/end)          └─ Pipecat pipeline per call
REST poll: queued outbound jobs           ──►            ├─ OpenAI Realtime (S2S + tools)
                                                         ├─ tool handlers → domain services
                                                         └─ AudioBufferProcessor → recordings
                                                   /api/... admin REST (tickets, jobs, calls)
                                                   /healthz
                                                   DB: SQLite (dev) / Postgres (Railway)
```

### 4.2 Repository layout

```
backend/
  pyproject.toml, uv.lock, .env.example, Dockerfile, alembic.ini
  src/carwash_voice/
    main.py                 FastAPI app factory, routers, lifespan
    config.py               pydantic-settings Settings
    logging.py              loguru setup, call_id correlation
    db/                     engine/session, models.py, alembic migrations
    domain/                 customers.py, tickets.py, calls.py, outbound.py (pure services)
    api/                    admin.py (REST), health.py, deps.py (auth)
    transports/
      local/                           LOCAL TESTING ONLY: /ws/local-bridge endpoint and
                                       serializer for the Bluetooth bridge's wire format
      (exotel/ or plivo/ in phase 2)   real CPaaS transports
    voice/
      providers/base.py                provider seam (build_llm_service(settings, tools))
      providers/openai_realtime.py
      prompts.py                       system prompt builder (persona, languages, mode)
      tools.py                         tool schemas + handlers calling domain services
      session.py                       builds and runs one call's pipeline
      recording.py                     audio/transcript persistence
    storage/                local.py (folder); interface ready for S3-compatible later
  tests/
local/                      LOCAL TESTING ONLY: phone <-> Bluetooth <-> Windows bridge
  README.md                 what this folder is, that it is throwaway test tooling
  spike/                    task 0 scripts (list devices, record, play, loopback)
  bridge/
    pyproject.toml, uv.lock, .env.example
    src/carwash_bridge/
      main.py               CLI entry (typer or argparse)
      devices.py            list/select audio devices by name substring
      audio_io.py           capture/playback with sounddevice, resampling (soxr)
      ws_client.py          WebSocket client, reconnects, protocol
      console.py            operator keys and prompts
      config.py
    tests/
  docs/
    spike-bluetooth.md      task 0 steps and results
    bridge-protocol.md      the wire protocol (section 4.3), kept in sync with code
    runbook-bridge.md       pairing, running the bridge, troubleshooting
docs/
  runbook-local.md          running the backend on the laptops
  runbook-railway.md        how to deploy
  decisions.md              short ADR-style notes for any change of plan
```

### 4.3 Bridge ↔ backend wire protocol (v1)

This protocol exists only for the local Bluetooth bridge. Its backend side lives in
`transports/local/`; the rest of the backend must not depend on it.

- Endpoint: `ws(s)://<host>/ws/local-bridge`. Auth: header `Authorization: Bearer <BRIDGE_TOKEN>`;
  reject with close code 4401 if missing or wrong. Never put the token in the URL.
- One WebSocket **per call**. The bridge opens it when the operator starts a call and
  closes it when the call ends.
- **Binary frames** = audio: PCM signed 16-bit little-endian, mono, **16 000 Hz**, 20 ms
  per frame (640 bytes). Both directions.
- **Text frames** = JSON control messages:

| Direction | Message | Meaning |
|---|---|---|
| bridge → backend | `{"type":"start","protocol":1,"call_id":"<uuid4>","direction":"inbound"\|"outbound","caller_number":"+91..."\|null,"outbound_job_id":"<id>"\|null,"bridge_id":"spare-laptop"}` | First message. Backend creates the call record and starts the pipeline. |
| bridge → backend | `{"type":"stop","reason":"operator_hangup"\|"remote_hangup"\|"error"}` | Call ended on the phone side. |
| bridge → backend | `{"type":"mark","name":"..."}` | Optional debug marker, logged only. |
| backend → bridge | `{"type":"ready","call_id":"..."}` | Pipeline is running; bridge starts sending audio. |
| backend → bridge | `{"type":"clear"}` | Customer interrupted the agent: flush the playback buffer immediately. |
| backend → bridge | `{"type":"end_call","reason":"..."}` | Agent finished. Bridge tells the operator to hang up (phase 1 can't hang up programmatically), then sends `stop` and closes. |
| backend → bridge | `{"type":"error","message":"..."}` | Fatal problem; bridge shows it and closes. |

Write this into `local/docs/bridge-protocol.md` and implement it with a Pipecat custom
`FrameSerializer` in `transports/local/` (check the base class and frame names in the
pinned Pipecat version; the built-in Twilio/Exotel/Plivo serializers are good
references). Call setup, the pipeline and tools in `voice/` must take a transport from
outside, so phase 2 can add `transports/exotel/` or `transports/plivo/` with Pipecat's
provider serializers without touching `voice/`.

### 4.4 Data model (first cut)

- `customers`: id, phone (E.164, nullable, unique when present), name, car_registration,
  preferred_language, created_at, updated_at.
- `tickets`: id, public_ref (human-friendly, e.g. `CW-24871`, short enough to say on the
  phone), customer_id, category (`quality`, `damage`, `billing`, `booking`, `other`),
  description, wash_location, wash_date, status (`open`, `in_progress`,
  `callback_requested`, `resolved`, `closed`), priority, created_via (`phone_inbound`,
  `phone_outbound`, `api`), created_at, updated_at.
- `ticket_events`: id, ticket_id, kind (`created`, `status_changed`, `note`,
  `callback_requested`, `customer_updated`), detail, actor (`agent`, `staff`), created_at.
- `calls`: id (= call_id uuid), direction, caller_number, started_at, ended_at,
  end_reason, language_detected, ticket_id (nullable), outbound_job_id (nullable),
  audio_path, transcript (JSON list of `{role, text, ts}`), summary (nullable, unused for now).
- `outbound_jobs`: id, customer_id, ticket_id (nullable), phone, purpose
  (`ticket_update`, `follow_up`), message (what the agent must convey), status (`queued`,
  `dialling`, `completed`, `no_answer`, `failed`), outcome_note, created_at, updated_at.

### 4.5 Agent tools (function calling)

All tool handlers call domain services (no SQL in `voice/`). Validate inputs; return
short, speakable results. Tools:

| Tool | Purpose |
|---|---|
| `find_customer(phone?, car_registration?)` | Look up an existing customer. |
| `upsert_customer(name, phone?, car_registration?, preferred_language?)` | Create or update. |
| `create_ticket(customer_id, category, description, wash_location?, wash_date?)` | Returns `public_ref`. |
| `get_ticket_status(public_ref? , phone?)` | Status of a ticket, or the latest open tickets for a phone. |
| `add_ticket_note(public_ref, note)` | Extra details given later in the call. |
| `request_human_callback(public_ref, reason, preferred_time?)` | Sets `callback_requested`. |
| `complete_outbound_job(job_id, outcome, note?)` | Outbound mode only. |
| `end_call(reason)` | Agent says goodbye first, then backend sends `end_call` to the bridge. |

### 4.6 Persona and prompt rules

- Open with: greeting with business and agent name, recording notice, then "How can I
  help?". Keep the recording notice short.
- Mirror the customer's language (English, Kannada, Hindi, Hinglish). If unclear, ask
  once: "Would you prefer English or Kannada?"
- Short spoken sentences; confirm critical details (phone number, car registration,
  ticket number) by reading them back; spell ticket refs clearly.
- Never invent ticket statuses or promises (refund amounts, times). If unsure, offer a
  human callback.
- Outbound mode: say who is calling and why, deliver the job's `message`, answer
  questions, record the outcome with `complete_outbound_job`.
- Prompt text lives in `voice/prompts.py`, built from settings (business name, agent
  name, languages) and call mode, so it can be tuned without code changes elsewhere.

### 4.7 Configuration (backend `.env.example` keys)

`APP_ENV`, `LOG_LEVEL`, `DATABASE_URL` (default `sqlite:///./data/dev.db`; convert
Railway's `postgresql://` to the driver URL in code), `OPENAI_API_KEY`,
`OPENAI_REALTIME_MODEL` (look up the current model name in OpenAI's docs; don't guess),
`OPENAI_REALTIME_VOICE`, `BRIDGE_TOKEN`, `ADMIN_API_KEY`, `BUSINESS_NAME`, `AGENT_NAME`,
`DEFAULT_LANGUAGE`, `RECORDINGS_DIR` (default `./data/recordings`), `RECORDING_RETENTION_DAYS`,
`MAX_CALL_SECONDS` (safety cap, e.g. 900), `PORT` (Railway sets it).

Bridge `.env.example` (in `local/bridge/`): `BACKEND_WS_URL`, `BACKEND_HTTP_URL`, `BRIDGE_TOKEN`, `BRIDGE_ID`,
`IN_DEVICE` and `OUT_DEVICE` (name substrings), `AUDIO_MODE` (`bluetooth` | `laptop`).

---

## 5. Tasks

### Task 0: Bluetooth bridge feasibility test — `PARKED`

**Goal:** prove that the spare Windows laptop can (a) hear the remote caller and (b) send
audio the caller hears, during a real SIM call, using only Windows' own Bluetooth
hands-free support. **No Windows Phone Link app**, no root. This decides go/no-go for
the local bridge.

You write the scripts and the instructions on the work laptop; the user runs them on the
spare laptop with the phone. You can build tasks 1–6 while waiting for the result.

Deliverables in `local/spike/` plus `local/docs/spike-bluetooth.md`:
- [x] `list_devices.py`: prints every audio device with index, host API (prefer WASAPI),
      channels and default sample rate. Highlights names containing "Hands-Free", "AG
      Audio" or the phone's name.
- [x] `record_call.py --device <substr> --seconds 15 --out caller.wav`: records from the
      chosen input during a call.
- [x] `play_into_call.py --device <substr> --wav prompt.wav`: plays a WAV (include a
      short spoken test clip or generate a tone sequence) into the chosen output.
- [x] `loopback_test.py`: records 5 s from the call, then plays it back into the call
      (caller hears themselves): a single combined check.
- [x] `local/docs/spike-bluetooth.md`: step-by-step for the user, in plain language:
      1. On the spare laptop, clone the repo and install Python 3.12 and `uv` (native
         Windows, not Docker or WSL).
      2. Make sure Phone Link is not handling calls: if it is installed, sign out or turn
         off its calls feature so it doesn't grab the call audio.
      3. Pair the phone with the laptop in Windows Bluetooth settings; on the phone,
         allow "Phone calls" for this device.
      4. Place a call from another phone to SIM 2 and answer it on the phone. Check the
         call audio moves to the laptop (on the phone's call screen, choose the laptop
         as the audio output if needed).
      5. Run `list_devices.py` before and during the call; note which devices appear
         only during the call. Then run the record, play and loopback scripts.
      6. Record the results in the table below.
      Also note: if Windows only exposes the call audio while some app holds the
      hands-free microphone open, say so (the bridge would then need to open the mic
      first to trigger the call audio link).
- [ ] Fill the result table and the go/no-go decision.

| Check | Result |
|---|---|
| Input device name / host API / sample rate | |
| Output device name / host API / sample rate | |
| Bridge hears the caller clearly | |
| Caller hears bridge audio clearly | |
| Audio quality (8 kHz narrowband or 16 kHz wideband) | |
| Noticeable echo / delay | |
| Anything that needed admin rights | |

**Go/no-go:** if it doesn't work, stop and ask the user. Their stated preference is to
move to an Indian CPaaS (Exotel or Plivo); the backend tasks still apply, only the
transport changes. A heavier alternative they may choose is booting Linux from a USB
stick on the spare laptop and using the Linux Bluetooth stack (BlueZ with PipeWire or
oFono), which is a better-documented hands-free setup. Don't attempt Docker or WSL for
Bluetooth: they need a custom Linux kernel and USB passthrough of the Bluetooth adapter.

Result: scripts and instructions written and lint-clean in `local/spike/` (own `pyproject.toml`; `list_devices.py` runs on the work laptop). PARKED: the user ran them twice on the spare laptop; the phone kept dropping the Bluetooth link (see section 7). The phone path is now Plivo.

---

### Task 1: Repo scaffolding, git, tooling — `DONE`

- [x] The user has set up git and the GitHub repo. Check `git status` and the branches;
      if `develop` doesn't exist yet, ask the user before creating it. Work on
      `feature/scaffold` off `develop`.
- [x] Root `.gitignore` covering `.env`, `*.db`, `data/`, `recordings/`, `.venv/`,
      `__pycache__/`, `.ruff_cache/`, `.pytest_cache/`, `*.wav` outside `tests/fixtures/`.
- [x] `backend/` and `local/bridge/` projects created with `uv init`, Python 3.12 pinned,
      Ruff + pytest + pytest-asyncio as dev dependencies, Ruff config per section 1.
- [x] `.env.example` in both projects (keys from section 4.7, placeholder values).
- [x] `.gitattributes` with `* text=auto eol=lf` (except `*.ps1` / `*.bat`: `eol=crlf`).
- [x] Short `docs/runbook-local.md` stub with the uv commands that worked on Windows.
- [x] `local/README.md` explaining that the folder is local test tooling only (Bluetooth
      bridge), and that the real call path is the CPaaS transport in the backend.
- [x] Ask the user, then make the first commit. Ask before pushing.

Acceptance: `uv run ruff check`, `uv run ruff format --check` and `uv run pytest` (with a
trivial test) pass in both projects on Windows.

Result: all files created; `ruff check`, `ruff format --check` and `pytest` pass in `backend/` and `local/bridge/` (and ruff in `local/spike/`). Git: repo had only the README on `main`; no `develop`, so I created `develop` locally from `main` (user said to commit what I want) and committed on `feature/scaffold`. Nothing pushed yet; ask before pushing, and `develop` does not exist on the remote.

---

### Task 2: Backend skeleton — `DONE`

- [x] `config.py` with pydantic-settings; fail fast with a clear message if required
      keys are missing (`OPENAI_API_KEY` only required when a call starts, so the API and
      tests run without it).
- [x] Logging with loguru (Pipecat already uses it): JSON lines in Railway, readable
      locally; bind `call_id` to every log line inside a call.
- [x] SQLAlchemy 2 models from section 4.4, Alembic set up with an initial migration;
      works on SQLite and Postgres (avoid SQLite-only or Postgres-only types; use
      `JSON` and string enums).
- [x] `GET /healthz` returns status and DB connectivity.
- [x] App factory, lifespan that runs migrations on start (configurable).

Acceptance: `uv run uvicorn carwash_voice.main:app` starts on Windows, `/healthz` is OK,
migrations create the tables in SQLite, tests cover config and health.

Result: `uv run uvicorn carwash_voice.main:app` starts on Windows; `/healthz` returns ok with DB check (503 if DB down); `/docs` works; migration `0001` creates all five tables in SQLite (string enums, JSON, no native enums, so Postgres-safe; Postgres itself not yet tested, do on Railway/Docker). 11 tests, ruff clean. Migrations run at start unless `RUN_MIGRATIONS_ON_START=false`. In non-dev `APP_ENV`, missing `ADMIN_API_KEY`/`BRIDGE_TOKEN` fails at startup.

---

### Task 3: Domain services + admin REST API — `DONE`

- [x] Domain services for customers, tickets (with `public_ref` generation that is
      unique, short and easy to say), ticket events, calls, outbound jobs.
- [x] Phone numbers normalised to E.164 with India as default region (use the
      `phonenumbers` library).
- [x] Admin REST under `/api`, protected by header `X-Admin-Key`:
      list/get/update tickets (status changes write a `ticket_events` row), list
      tickets with `status=callback_requested`, get customer, list calls with transcript,
      download a call's audio, create/list outbound jobs.
- [x] Bridge-facing `GET /api/bridge/outbound-jobs/next` and
      `POST /api/bridge/outbound-jobs/{id}/status`, protected by the bridge token.
- [x] Tests for every service function and endpoint (SQLite in a temp dir).

Acceptance: tests pass; OpenAPI docs at `/docs` show all endpoints.

Result: services in `domain/` (customers, tickets, calls, outbound, phone, errors); admin API in `api/admin.py` (admin key) and bridge endpoints (bearer token); 41 tests pass, ruff clean, `/docs` lists every endpoint. Ticket refs are `CW-` plus 5 digits (accepts spoken forms like `cw 24871`). Missing admin key or bridge token on the server gives 503, wrong or missing credentials 401. Outbound job completion also writes a note on the ticket. Bridge `next` endpoint returns 204 when the queue is empty and does not change the job status; the bridge then posts `dialling`.

---

### Task 4: Local-bridge protocol, serializer, call session lifecycle — `DONE`

- [x] `local/docs/bridge-protocol.md` from section 4.3.
- [x] In `transports/local/`: `LocalBridgeFrameSerializer` (Pipecat `FrameSerializer`
      subclass): binary → input audio
      frames at 16 kHz mono; output audio frames → binary (resample to 16 kHz if the
      pipeline's output rate differs); interruption frame → `{"type":"clear"}`;
      end-of-call → `{"type":"end_call"}`. Verify frame class names in the pinned version.
- [x] `/ws/local-bridge` endpoint (in `transports/local/`): auth check, wait for `start`
      (timeout 5 s), then hand over to the transport-neutral call session in
      `voice/session.py`, which creates the `calls` row, builds the pipeline, runs until
      `stop`, disconnect, `end_call` or `MAX_CALL_SECONDS`, and always finalises the call
      row. The local transport sends `ready` once the pipeline is running.
- [x] Route registration for `transports/local/` sits behind a setting
      (`ENABLE_LOCAL_BRIDGE`, default true in dev) so it can be switched off on Railway
      once CPaaS is live.
- [x] Pipeline factory is injectable so tests can replace the AI provider with a fake
      that echoes audio or emits canned frames.
- [x] Tests: protocol happy path, bad token (4401), missing `start`, abrupt disconnect
      still finalises the call row; a test client streams a WAV fixture and receives audio.

Acceptance: the fake-provider WebSocket tests pass without network access.

Result: 55 tests pass offline (14 for the bridge: happy path with a generated 1 s WAV and audio echoed back, agent `end_call`, bad token, token in URL refused, missing or bad `start`, abrupt disconnect finalises the call, `MAX_CALL_SECONDS`, no provider, route off when disabled). `voice/session.py` (`run_call`, `CallHandle`, `CallContext`) is transport-neutral, so a CPaaS transport only needs to build a Pipecat transport and call it. Provider seam is `voice/providers/base.py` (`VoiceProvider.build`). Tests inject `tests/fakes.py` EchoProvider through `create_app(settings, provider)`. End reasons: stop reason, `remote_hangup` on drop, `max_duration`, agent reason. Not yet done: nothing; the real provider is task 5.

---

### Task 5: Voice agent (OpenAI Realtime) — `DONE`

- [x] Provider seam `providers/base.py` and the OpenAI Realtime implementation using
      Pipecat's OpenAI Realtime service (check its current class name and session
      config). Use server-side voice activity detection and enable interruptions.
- [x] Prompt builder per section 4.6, separate inbound and outbound variants; outbound
      variant includes the job's customer name, ticket ref and message.
- [x] Tools per section 4.5 with JSON schemas and handlers; handlers run DB work off the
      event loop (async session or thread) so audio never stalls.
- [x] `end_call` flow: agent speaks goodbye, waits for that audio to finish playing, then
      the backend sends `end_call`.
- [x] A live smoke test (`pytest -m live`, skipped by default) that opens a real
      session with a WAV of a short English complaint and asserts a ticket was created.

Acceptance: unit tests for tools and prompt builder pass; the live smoke test passes when
the user provides `OPENAI_API_KEY` (ask them to run it or to put the key in `.env`).

Result: 75 offline tests pass (prompts, every tool body, async wrappers, schemas per direction, `GreetOnConnect`, `EndCallWatcher` incl. timeout, provider build, app wiring). Live smoke test (`uv run pytest -m live -s`, skipped by default) passed 3 of 3 runs after the prompt was tightened: the agent greets first, takes the complaint from a generated English clip and creates a ticket (about 50 s per run including the scripted yes). Model `gpt-realtime-2.1`, voice `marin`. Not yet tested live: the `end_call` goodbye flow (covered by unit tests only), outbound calls, Kannada/Hindi (task 10).

---

### Task 6: Recording — `DONE`

- [x] Record both sides with Pipecat's audio buffer processor; save a WAV per call
      (stereo: left caller, right agent, if supported; otherwise mixed mono) under
      `RECORDINGS_DIR/<yyyy>/<mm>/<call_id>.wav`; store the path on the call row.
- [x] Transcript: collect user and assistant transcription events from the Realtime
      service into `calls.transcript` with timestamps.
- [x] Storage behind a small interface (`save(call_id, bytes) -> path`, `open(path)`) so
      an S3-compatible store can be added later; implement local only.
- [x] Retention: a CLI command `uv run carwash-voice purge-recordings` deleting audio
      older than `RECORDING_RETENTION_DAYS`.

Acceptance: a fake-provider test call produces a WAV and a transcript row.

Result: done. `run_call` puts an `AudioBufferProcessor` after the transport output and saves a
16 kHz stereo WAV (caller left, agent right) via `LocalRecordingStore` (`voice/recording.py`,
interface `save/open/delete`) to `RECORDINGS_DIR/yyyy/mm/<call_id>.wav`; the relative path goes
to `calls.audio_path`. Transcript turns come from the aggregators' `on_user_turn_message_added`
and `on_assistant_turn_stopped` events into `CallHandle.transcript` (role, text, ISO time) and
are saved by `finalize_call`. `uv run carwash-voice purge-recordings` removes audio older than
`RECORDING_RETENTION_DAYS` and keeps transcripts. Surprises: Pipecat runs event handlers as
tasks, and on a hang-up the cancel may not reach the recorder, so `run_call` flushes the
recorder itself in `finally` (best effort, must never block finalising the call; a
`CancelledError` there must be caught). Not verified live: the transcript from a real OpenAI
call.


---

### Task 7: Bridge app in `local/bridge/` (Windows) — `DONE`

- [x] `carwash-bridge devices`: list devices (reuse task 0 code from `local/spike/`).
- [x] `carwash-bridge run`: operator console loop:
      - `a` = inbound call answered (prompt for optional caller number, Enter to skip),
      - `o` = fetch next outbound job, show "Dial <number> on SIM 2, press Enter when
        they answer", mark job `dialling`, then start the call,
      - `e` = call ended (sends `stop`), `q` = quit.
      Show clear status lines (connected, agent speaking, `end_call` received → "Agent
      finished, please hang up the phone, then press e").
- [x] Audio: capture from `IN_DEVICE`, play to `OUT_DEVICE` via `sounddevice` (WASAPI),
      at the device's native rate; resample to/from 16 kHz with `soxr`; 20 ms frames;
      playback jitter buffer (~60–100 ms) that is flushed on `clear`.
- [x] `AUDIO_MODE=laptop` uses the default mic and speakers so anyone can test the bot
      on a laptop with a headset, no phone needed (use a headset to avoid echo).
- [x] WebSocket client with auth header, ping/keepalive, clean shutdown, clear errors if
      the backend is down. Never log the token.
- [x] Tests: framing and resampling, protocol handling with a fake server.

Acceptance: laptop mode talks to a local backend running the fake provider (audio echo)
and to the real provider.

Result: done in code. `local/bridge/src/carwash_bridge/`: `audio.py` (framer, soxr resampler, jitter
buffer), `client.py` (protocol v1 client with clear error messages), `audio_io.py` (sounddevice),
`app.py` (console: a, o, e, q), `cli.py` (`carwash-bridge devices|run`). 12 offline tests pass,
Ruff clean, `devices` lists this laptop's devices. NOT tried with a real microphone yet: the user
should follow `docs/runbook-local.md` and report echo, latency and audio quality. The websockets
17 connection has `close_code`, not `rcvd`.


---

### Task 8: Local end-to-end — `MOSTLY DONE` (laptop-mic only; phone part replaced by Plivo, task 12)

- [ ] Laptop mode on the work laptop: backend and bridge both on localhost, talk to the
      agent through a headset, create a ticket, check it via the admin API.
- [ ] Phone mode on the **spare laptop** (tell the user beforehand): backend and bridge
      both on the spare laptop (localhost, avoids firewall changes; the backend may run
      natively or in Docker there, the bridge always natively). Call SIM 2 from another
      phone, answer, press `a`, run the complaint flow, then the status lookup flow, then
      a human-handoff request.
- [ ] Write `docs/runbook-local.md` (backend) and `local/docs/runbook-bridge.md` (pairing,
      bridge, troubleshooting) fully.
- [ ] Record latency observations (time from caller stopping speaking to agent audio)
      and any audio quality issues in section 6.

Acceptance: all three inbound flows work on a real phone call; tickets, transcripts and
audio are stored.

Result: _(fill in)_

---

### Task 9: Outbound update calls — `CODE DONE`

- [ ] Admin API creates an outbound job for an existing ticket with a message.
- [ ] Bridge `o` flow: operator dials manually, presses Enter when answered; agent runs
      the outbound prompt, delivers the message, answers questions, calls
      `complete_outbound_job`; job status and ticket events update.
- [ ] Handle "no answer" (operator marks it from the console) and "customer busy, call
      later" (agent records outcome and suggested time).

Acceptance: one real outbound call completes and the job, call and ticket rows reflect it.

Re-scoped (Plivo, not the bridge): `POST /api/outbound-jobs/{id}/dial` (admin key) marks the
job dialling and asks Plivo (`transports/plivo/dialer.py`, httpx, fields confirmed from the
installed `plivo` SDK) to call the customer with answer URL `/plivo/answer?job_id=<id>` and hangup URL
`/plivo/hangup?job_id=<id>`. The hangup webhook (signature checked) marks unanswered/busy/failed
calls `no_answer`/`failed`. An answered call finishes through the agent's
`complete_outbound_job`. Also fixed: `GET /api/calls/{id}/audio` now resolves the relative
recording path. 104 offline tests pass. Still to verify live: one real outbound call end to
end (the acceptance), Plivo's real response and form fields, calling hours policy (none
enforced yet; research says service calls have no TRAI time limit but avoid late-night calls).


---

### Task 10: Language check — `TODO`

- [ ] With the user, run short scripted calls in English, Kannada, Hindi and Hinglish
      (write the scripts in `docs/language-test.md`). The user judges understanding,
      pronunciation and naturalness on a 1–5 scale; record scores and notes.
- [ ] If Kannada is poor, write up options in `docs/decisions.md` for the user to choose
      (for example: Gemini Live, or a cascade of an Indian STT/TTS provider such as
      Sarvam AI with an LLM in the middle) with what each would change in the code. Do
      not switch provider without the user's decision.

Acceptance: score table filled; decision recorded.

Result: _(fill in)_

---

### Task 11: Railway deployment — `FILES DONE`

- [ ] `backend/Dockerfile` (multi-stage with uv, non-root user, listens on `$PORT`),
      `railway.json` (or `railway.toml`) with health check `/healthz`.
- [ ] Railway Postgres; `DATABASE_URL` handled; migrations run on deploy.
- [ ] Railway volume mounted for `RECORDINGS_DIR` (container disk is ephemeral).
- [ ] Region: an Asia region if offered (check Railway's current list).
- [ ] Variables set in Railway (names only in docs; the user enters values).
- [ ] `docs/runbook-railway.md`: create project, add Postgres and volume, set variables,
      deploy from GitHub, check logs, roll back.
- [ ] Ask the user before anything that creates paid resources.

Acceptance: `/healthz` OK on the Railway URL; laptop-mode bridge on the work laptop holds
a conversation with the Railway backend over `wss://`.

Result so far: `backend/Dockerfile` (multi-stage uv, non-root, `$PORT`), `backend/railway.toml`,
`backend/.dockerignore`, `docs/runbook-railway.md`. Verified: app starts with `APP_ENV=production`
(local bridge route absent, Plivo 503 when unconfigured, `/healthz` OK). NOT verified: the Docker
build (no Docker on the work laptop; try on the spare laptop), Postgres, the volume
permissions (`RAILWAY_RUN_UID=0` if needed), Railway region names and price. The user must
create the Railway project, Postgres and volume (paid resources: ask first), then set variables.


---

### Task 12: Railway ↔ phone end-to-end — `TODO`

- [ ] Spare-laptop bridge points at the Railway backend; repeat task 8 phone flows and
      one outbound call.
- [ ] Compare latency with the local run; note it in section 6.
- [ ] Decide with the user whether Railway is suitable or a VPS is needed; record in
      `docs/decisions.md`.

Acceptance: all phase 1 flows work through Railway on a real phone call.

Result: _(fill in)_

---

### Task 13: Hand-off pack for Opus review — `TODO`

- [ ] README "Setup and run" section filled in.
- [ ] Section 6 below complete (versions, class names, surprises, open risks).
- [ ] List of known limitations and the phase 2 plan updated.
- [ ] All lint and tests green; summary of test coverage by area.
- [ ] Tell the user the branch is ready for an Opus review against `develop`.

Result: _(fill in)_

---

### Parked: phase 1c and phase 2 (outline, do not start)

- **1c Companion Android app (Kotlin, no root):** foreground service with
  `ANSWER_PHONE_CALLS` / `CALL_PHONE`; auto-answer calls on SIM 2, dial on command from
  the backend using SIM 2's phone account, report caller number and call state to the
  backend. Removes the manual operator steps.
- **2 CPaaS:** Indian provider (Exotel or Plivo; compare KYC, number cost, per-minute
  price, bidirectional media streaming). Add `/ws/<provider>` using Pipecat's provider
  serializer; inbound webhook to start the stream; outbound calls through the provider's
  API; concurrent calls. Optionally forward SIM 2 to the CPaaS number during migration.
- **Later:** call summaries for human agents, staff notifications (WhatsApp/email),
  Tamil/Telugu/Marathi, an S3-compatible recording store, a small staff web page.

---

## 6. Verified facts / surprises (fill in as you go)

| Date | Fact or surprise | Source / how verified |
|---|---|---|
| 2026-11-22 | Third-party Android apps can't capture SIM call audio (needs privileged `CAPTURE_AUDIO_OUTPUT`); no public API to inject audio into a call. Root-free SIM-to-SIP apps were not found. | Android developer docs; gsm2sip README (needs root). |
| 2026-11-22 | Windows exposes Bluetooth HFP as a "Hands-Free" input/output endpoint pair that apps can open; not yet proven for capturing the remote side of a phone call. | Microsoft Bluetooth classic audio docs. Task 0 verifies. |
| 2026-11-22 | Work laptop: Python 3.12.10 via `py -3.12`; `uv` was missing, installed with `py -3.12 -m pip install --user uv` (uv 0.13.9, Scripts folder not on PATH, so run `py -3.12 -m uv ...`). Ruff 0.17.6. Pipecat/OpenAI/FastAPI versions not pinned yet (task 2 onward). | Ran the commands. |
| 2026-11-22 | `phonenumbers` 9.0.44 added for E.164 (India default). Pinned in `backend/uv.lock`: FastAPI 0.165.0, SQLAlchemy 2.1.9, Alembic 1.20.1, loguru 0.8.0, pydantic-settings 2.16.3, psycopg 3.3.9, httpx 0.28.1 (tests). Starlette warns that `httpx` in TestClient is deprecated in favour of `httpx2`; harmless for now. | `uv.lock`, test run. |
| | Pinned versions (Pipecat, OpenAI model) | |
| 2026-11-22 | Pipecat **1.16.0** (`pipecat-ai[openai,websocket,silero]`). It needs `loguru<0.8`, so loguru is pinned `>=0.7.3,<0.8` (0.7.3 installed). `PipelineTask`/`PipelineRunner` are deprecated aliases: use `PipelineWorker` (`pipecat.pipeline.worker`) and `WorkerRunner` (`pipecat.workers.runner`, `add_workers()` then `run()`). | Read installed source; deprecation warnings. |
| 2026-11-22 | Classes used: `FrameSerializer` (`serialize`/`deserialize`, `_resample_audio_in/out`, `_reset_audio_out`, params `audio_in/out_sample_rate`), `FastAPIWebsocketTransport` + `FastAPIWebsocketParams` (events `on_client_connected`, `on_client_disconnected`), frames `InputAudioRawFrame`, `OutputAudioRawFrame`, `InterruptionFrame`, `OutputTransportMessageFrame`, `OutputTransportMessageUrgentFrame`, `EndFrame`; `PipelineParams(audio_in_sample_rate, audio_out_sample_rate)`. Built-in `ExotelFrameSerializer` and `PlivoFrameSerializer` exist (8 kHz default), which helps the CPaaS move. OpenAI Realtime service is `pipecat.services.openai.realtime.llm.OpenAIRealtimeLLMService` (default model string in Pipecat is `gpt-realtime-2.1`: still to verify in OpenAI docs, task 5). | Read installed source. |
| 2026-11-22 | OpenAI: the key works; models listed for it include `gpt-realtime-2.1` (used), `gpt-realtime-2.1-mini`, `gpt-realtime-2`, `gpt-realtime-1.5`, `gpt-realtime`, `gpt-realtime-mini`. The user's pasted settings had `OPENAI_REALTIME_MODEL=marin` (a voice, not a model) and TTS keys (`ACTIVE_MODEL`, `TTS_SPEED`) from another project; fixed the model and set voice to `marin`; the TTS keys are ignored (they belong to a cascade). | Models API call, live test. |
| 2026-11-22 | Live behaviour: first prompt version made the agent recap everything for ~19 s and wait for a yes (2 of 4 early runs timed out). Fixed in `voice/prompts.py`: max 1-2 short sentences per turn, no recap or permission request when details are already given. Pipecat realtime notes: user turns come from OpenAI server VAD; context aggregator auto-enters realtime mode; an `LLMRunFrame` after `ClientConnectedFrame` makes the agent speak first. Latency not measured yet. | Debug logs. |
| 2026-11-22 | Starlette test client: `ws.receive()` returns a close as a `websocket.close` message instead of raising; use that to assert close codes. | Test debugging. |

## 7. Decisions log (changes to the plan)

| Date | Decision | Why | Approved by |
|---|---|---|---|
| 2026-11-22 | Initial plan (section 3) | User answers to planning questions | User |
| 2026-11-22 | No Windows Phone Link; Bluetooth bridge code in `local/` (+ `transports/local/`); spare laptop runs phone tests; user sets up git | User follow-up | User |
| 2026-11-22 | **Switch to CPaaS for the phone path.** Bluetooth bridge (task 0) is parked: the OnePlus phone kept disconnecting from the spare laptop. What was learned: Windows did expose the phone as `Hands-Free HF Audio` input/output (WDM-KS, 8 kHz mono), so a retry later is plausible. Consequences: the provider (Exotel or Plivo) must be chosen by the user; the CPaaS transport moves from phase 2 into the main plan; `local/` keeps only laptop-mic mode for phone-free testing; tasks 7, 8, 9 and 12 are re-scoped when the CPaaS transport is built. Until the user picks a provider, tasks 4 to 6 are built transport-neutral. | User unable to keep the Bluetooth link up | User |


## Plivo transport notes (2026-11-22)

- `backend/src/carwash_voice/transports/plivo/`: `endpoint.py` (`POST /plivo/answer`,
  `WS /ws/plivo/{secret}`), `signature.py`. Settings: `PUBLIC_BASE_URL`, `PLIVO_AUTH_ID`,
  `PLIVO_AUTH_TOKEN`, `PLIVO_WS_SECRET`, `PLIVO_NUMBER`; `Settings.plivo_enabled`.
- New dependencies: `plivo` (SDK; its `validate_v3_signature` is used, and its source says it also
  accepts a ws/wss URL, so Plivo may sign the WebSocket handshake too; unverified) and
  `python-multipart` (form parsing).
- The WebSocket is protected by the secret path segment. Signature checks cover the answer URL.
- Unverified against real Plivo: that `start.extra_headers` carries our `extraHeaders`; that
  `contentType` without `;rate=8000` is accepted from the serializer; that the hang-up request
  does not cut off the goodbye; the exact `Direction`/`From`/`To` form fields. Tests fake all of
  these from the documentation.
- Tests: `backend/tests/test_plivo.py` (12). The hang-up call is mocked; never let tests reach Plivo.

---

## 8. Opus review (2026-11-22)

Opus reviewed the code and this tracker at the pause point. Verified by Opus: 104 backend + 12
bridge tests passed and Ruff was clean before the review; no `.env` or key-like strings are in
git. R1 to R7 were fixed by Opus (uncommitted until the user approves); after the fixes: 114
backend + 12 bridge tests pass, Ruff clean, the call tests passed three runs in a row.
**Your work: R8 to R12, then keep R1, R3 and R4 in mind during the first live Plivo calls.**

| # | Finding | Status |
|---|---|---|
| R1 | Plivo call context (direction, customer number, outbound job id) relied only on Plivo echoing `extraHeaders` in the media `start` event, which nothing verifies (Pipecat never parses it). If wrong, outbound calls would run with the inbound prompt and no job. | FIXED: `/plivo/answer` stores the context in memory keyed by `CallUUID` (`PendingCalls`, 5 min expiry); the socket looks it up by `start.callId` first and falls back to `extra_headers`. It logs `Plivo call details from: ...`. **Check that log line on the first real call**: it proves whether `callId` equals `CallUUID`. Memory store assumes one server process (true on Railway with one replica). |
| R2 | An answered outbound call where the customer hangs up before the agent calls `complete_outbound_job` left the job `dialling` for ever (hang-up webhook ignores `completed`); redial gave 409 and only the bridge token could reset it. | FIXED: `run_call` marks a still-`dialling` job `failed` with a note when the call ends (`outbound.close_unfinished_job`, inside the same shielded unit as `finalize_call`, because cancellation skipped code after the first shielded await). New admin route `POST /api/outbound-jobs/{id}/status` lets staff re-queue. |
| R3 | `end_call` flow: prompt says "say goodbye, then call end_call", the tool result said "Say a brief goodbye now", and Pipecat always asks the model for a new response after a tool result: likely a double goodbye, or 20 s of silence if the model stays quiet. | FIXED: `EndCallWatcher` now tracks `BotStarted/StoppedSpeakingFrame`. If the agent is speaking when armed, the call ends when that speech stops; if silent, it waits up to 5 s (`silence_secs`) for a goodbye to start, then ends when it stops; 20 s cap. Tool result now says "if you already said goodbye, say nothing more". **Still verify live** (task 5 note). |
| R4 | Privacy (DPDP): any caller could hear any ticket's status and description by saying a 5-digit number, add notes or flag callbacks on it; `find_customer` by car registration revealed another customer's name and tickets; `upsert_customer` matched by registration overwrote that customer's phone with the caller's. | FIXED: ticket tools need the call to come from the customer's own number, or a matching `car_registration` as a second detail (new optional tool argument); a confirmed customer stays confirmed for the rest of the call. `find_customer` returns nothing unless confirmed. `upsert_customer` creates a separate customer instead of replacing a stored number. Prompt has a privacy rule. Known gap: a call with **no** caller number (local bridge) that upserts by registration can still rename that customer; acceptable for local testing. **Check live** that the agent asks for the registration naturally when a tool returns the privacy error. |
| R5 | Bridge (local only): pressing `e` on an outbound call always posted `completed`, overwriting the agent's outcome. | FIXED: the bridge no longer sets a status; the backend handles unfinished jobs (R2). |
| R6 | `POST /api/outbound-jobs/{id}/dial` did DB work on the event loop and two quick requests could both pass the "queued" check (double call). | FIXED: `outbound.claim_for_dialling` (one conditional UPDATE, `ConflictError` → 409); all DB work via `run_db`. |
| R7 | The Plivo media socket's secret path segment would appear in uvicorn's WebSocket log lines on Railway. | FIXED: `RedactSecretPaths` filter on `uvicorn.error` / `uvicorn.access` replaces it with `/ws/plivo/***`. |
| R8 | README is behind the Plivo switch: the diagram and roadmap still show Bluetooth as phase 1 and "Exotel or Plivo" as phase 2; layout says "planned"; no "Setup and run" section. | TODO (Sonnet, fold into task 13) |
| R9 | `docs/decisions.md` (asked for in tasks 10 and 12) does not exist; the decisions live in section 7. Either create it or change tasks 10 and 12 to use section 7. | TODO (Sonnet) |
| R10 | Section 6 has an empty "Pinned versions" row; tasks 9 and 11 checkboxes are unticked although their Result lines describe the code as done. Tick what is done, leave the live-test boxes open. | TODO (Sonnet) |
| R11 | Small, optional: admin list endpoints accept any `limit` (cap at e.g. 500); `purge_recordings` skips calls that never got `ended_at`; no minimum length check on `PLIVO_WS_SECRET` (suggest >= 24 chars and say so in `docs/plivo-setup.md`). | TODO (Sonnet, low priority) |
| R12 | Before the first live call, add these to the "Not yet verified" list and check them: the R1 log line, the goodbye timing (R3), the privacy prompt behaviour (R4), and that a hang-up mid-outbound marks the job failed (R2). | TODO (Sonnet) |
| R13 | Second review (an independent Opus agent, on R1 to R7 only) found: (a) `upsert_customer` marked whatever record it matched as verified, so saying a victim's phone, or giving their registration on a call with no caller number, unlocked and overwrote their record; (b) `create_ticket` accepted any model-supplied `customer_id`; (c) the log filter broke uvicorn's access formatter (it unpacks 5 args); (d) staff could re-queue a still-dialling job (second live call); (e) `close_unfinished_job` read-then-wrote (race with the agent's outcome); (f) "not found" vs privacy error let callers probe which tickets and numbers exist. | FIXED by Opus: (a) the tool now only updates the caller's own record (confirmed in this call, or matching the caller's number); everything else is a new customer (`customers.create_customer` / `update_customer`; a said number already owned by someone is not attached); (b) only a confirmed id is used; (c) the filter keeps the args shape, with a test through `AccessFormatter`; (d) 409 unless `?force=true`; (e) conditional UPDATE; (f) one `PRIVACY_ERROR` for both. 8 new tests; 122 backend tests pass. |
