# Phone Call AI (car-wash customer voice agent)

A backend that lets customers **phone a normal mobile number and talk to an AI agent**.
The agent speaks English, Kannada, Hindi and Hinglish, takes complaints, raises tickets,
reads back ticket status, makes outbound update calls, and flags calls that need a human.

It starts as a hobby prototype, but it is meant to become the real customer line for a
car-wash business. The code is general: the business name, agent persona and tools are
configuration, not hard-coded.

> **Status:** planning done, implementation not started. Work is tracked in
> [TASKS.md](TASKS.md).

---

## What it does (phase 1 scope)

| Feature | What happens on the call |
|---|---|
| Inbound complaint → ticket | Customer calls, the agent collects name, car registration, wash location/date and the complaint, creates a ticket and reads back the ticket number. |
| Ticket status lookup | Customer asks about an existing ticket (by number or phone), the agent reads the status. |
| Outbound update call | Staff queue an update (e.g. "refund approved"); the agent calls the customer, explains, answers questions, logs the outcome. |
| Human handoff request | If the customer asks for a person, the ticket is marked *callback requested* and the agent promises a call back. (Live transfer is not possible with one SIM.) |

Every call stores **audio, transcript and the ticket**. The agent announces at the start
that the call is recorded. A summary for human agents is planned but not in phase 1.

---

## Why the architecture looks like this

### The Android constraint

Android does **not** let a normal app hear or speak into a SIM phone call. Capturing call
audio needs the `CAPTURE_AUDIO_OUTPUT` permission, which only system/vendor apps get
([Android docs](https://developer.android.com/media/platform/sharing-audio-input)), and
there is no public API to inject audio into a call. The SIM-to-SIP "gateway" apps that
exist (for example [gsm2sip](https://github.com/pulpoff/gsm2sip)) need a rooted phone.

### The workaround: a Bluetooth "car-kit" bridge on Windows

The phone stays stock and unrooted. A spare **Windows laptop** pairs with it over
Bluetooth as a hands-free device, exactly like a car stereo. Windows then exposes the
call as a "Hands-Free" microphone/speaker pair
([Microsoft docs](https://learn.microsoft.com/windows-hardware/drivers/bluetooth/bluetooth-classic-audio)).
A small Python **bridge** program reads the caller's voice from that device, streams it
to the backend over a WebSocket, and plays the AI's reply back into the call.

The Windows Phone Link app is **not** used; only Windows' own Bluetooth hands-free
support.

This route is documented in pieces but not proven end to end for this use, so the
**first task is a feasibility test** (see TASKS.md, task 0). If it fails, the plan moves
to a CPaaS provider.

The Bluetooth bridge is **local test tooling only**, for checking the flow and getting a
feel for the agent. All of its code lives in the top-level `local/` folder (plus a small
adapter in the backend's `transports/local/`), so it can be dropped later. The real,
long-term call path is a CPaaS transport inside the normal backend structure.

```
                         PHASE 1 (SIM in an Android phone)

 Customer ──GSM call──► Android phone (stock, SIM 2)
                              │  Bluetooth hands-free (HFP)
                              ▼
                    Spare Windows laptop: "bridge"  (local/ folder)
                    (Python, sounddevice/WASAPI, no Phone Link)
                              │  WebSocket: PCM16 mono 16 kHz + JSON control
                              ▼
          Backend (FastAPI + Pipecat)  ── laptop first, Railway later
             │                 │
             ▼                 ▼
   OpenAI Realtime       SQLite (local) / Postgres (Railway)
   speech-to-speech      customers, tickets, calls, outbound jobs
   + tool calls          + recordings (local folder / Railway volume)


                         PHASE 2 (CPaaS, concurrent calls)

 Customer ──PSTN──► Indian CPaaS number (Exotel or Plivo)
                              │  provider media-stream WebSocket
                              ▼
          Same backend, new transport adapter (bridge no longer needed)
```

### Key choices

| Decision | Choice | Reason |
|---|---|---|
| Backend stack | Python 3.12, FastAPI, [Pipecat](https://github.com/pipecat-ai/pipecat) | Pipecat handles real-time audio pipelines, interruptions and has ready adapters for CPaaS providers, so phase 2 is a transport swap. |
| AI voice | OpenAI Realtime (speech-to-speech) behind a swappable interface | Lowest latency, natural turn-taking, tool calling for tickets. Kannada quality must be tested; fallbacks are Gemini Live or an Indian STT/TTS cascade (e.g. Sarvam AI). |
| Bridge | Python on the spare Windows laptop | No admin, no Linux, no root. WSL/Docker cannot reach the laptop's Bluetooth without admin rights and extra drivers. |
| Call answering/dialling | Manual in phase 1 (tap Answer / dial on the phone itself) | Keeps phase 1 small. A companion Android app can automate it later. |
| Machines | Work laptop: coding, unit tests, laptop-mic testing. Spare laptop (admin, Docker): Bluetooth bridge and all real phone tests. | The bridge must sit near the phone; the spare laptop has no company restrictions. |
| Data | SQLAlchemy 2 + Alembic; SQLite locally, Postgres on Railway | Same code in both places. |
| Hosting | Laptop → Railway (Asia region) → Railway + CPaaS, or a VPS if Railway is unsuitable | Railway supports WebSockets, Postgres and volumes. |
| Country | India | Affects CPaaS choice (Exotel/Plivo, KYC for numbers) and languages. |

---

## Roadmap

| Phase | Goal |
|---|---|
| 0 | Feasibility test: can a Windows laptop capture and inject call audio over Bluetooth? |
| 1a | Backend + bridge on the spare laptop, talking to the phone over Bluetooth. Also a "laptop mic" mode to test without a phone. |
| 1b | Backend on Railway, bridge on the spare laptop connecting over the internet. |
| 1c (optional) | Companion Android app to auto-answer, dial on command and report caller ID. |
| 2 | Indian CPaaS (Exotel or Plivo) number streaming to the same backend; concurrent calls. |
| Later | Call summaries for human agents, notifications (WhatsApp/email), more regional languages (Tamil, Telugu, Marathi). |

---

## Repository layout (planned)

```
backend/        FastAPI + Pipecat service (deployable to Railway)
  .../transports/local/   backend side of the Bluetooth bridge (local testing only)
  .../transports/<cpaas>/ real phone transports (phase 2)
local/          LOCAL TESTING ONLY: Bluetooth spike scripts, Windows bridge app, its docs
docs/           Backend runbooks, decisions
TASKS.md        Implementation plan + tracker (input prompt for the coding agent)
```

Setup and run instructions will be added here as each part is built.

---

## Secrets and personal data

- API keys and tokens live in `.env` (git-ignored) locally and in Railway variables in
  the cloud. Nothing secret is committed.
- Call recordings, transcripts and phone numbers are personal data (India's DPDP Act
  applies). Retention is configurable and access to the admin API is key-protected.
