"""Operator console: start and end calls, and pump audio between the sound card and backend."""

from __future__ import annotations

import asyncio
import contextlib

import httpx

from carwash_bridge.audio_io import LiveAudio, list_devices
from carwash_bridge.client import BridgeCall, BridgeError, CallRequest
from carwash_bridge.config import BridgeSettings

HELP = "a = answer inbound call | o = next outbound job | e = end call | q = quit"


def say(text: str) -> None:
    print(text, flush=True)


async def ask(prompt: str) -> str:
    return (await asyncio.get_running_loop().run_in_executor(None, input, prompt)).strip()


class Console:
    def __init__(self, settings: BridgeSettings) -> None:
        self._s = settings
        self._audio: LiveAudio | None = None
        self._call: BridgeCall | None = None
        self._pump: asyncio.Task[None] | None = None
        self._job_id: int | None = None

    # --- backend helpers ---------------------------------------------------------------------

    async def _job_status(self, status: str, note: str | None = None) -> None:
        if self._job_id is None:
            return
        body = {"status": status, "outcome_note": note}
        async with httpx.AsyncClient(base_url=self._s.http_url, timeout=10) as http:
            await http.post(
                f"/api/bridge/outbound-jobs/{self._job_id}/status",
                json=body,
                headers={"Authorization": f"Bearer {self._s.token}"},
            )

    async def _next_job(self) -> dict | None:
        async with httpx.AsyncClient(base_url=self._s.http_url, timeout=10) as http:
            try:
                r = await http.get(
                    "/api/bridge/outbound-jobs/next",
                    headers={"Authorization": f"Bearer {self._s.token}"},
                )
            except httpx.HTTPError as exc:
                raise BridgeError(f"Cannot reach the backend at {self._s.http_url}: {exc}") from exc
        if r.status_code == 204:
            return None
        if r.status_code == 401:
            raise BridgeError("The backend rejected the token (check BRIDGE_TOKEN).")
        r.raise_for_status()
        return r.json()

    # --- a call ------------------------------------------------------------------------------

    async def _begin(self, req: CallRequest) -> None:
        audio = LiveAudio(self._s.in_device, self._s.out_device)
        call = BridgeCall(
            self._s.ws_url,
            self._s.token,
            self._s.bridge_id,
            on_audio=audio.play,
            on_clear=audio.clear,
            on_end_call=lambda reason: say(
                f"Agent finished ({reason}). Hang up the phone, then press e."
            ),
            on_error=lambda m: say(f"Backend error: {m}"),
        )
        call_id = await call.start(req)
        audio.start()
        self._audio, self._call = audio, call
        self._pump = asyncio.create_task(self._send_mic(audio, call))
        say(f"Connected. Call {call_id[:8]}. Audio: {audio.describe()}. Speak now (use a headset).")

    async def _send_mic(self, audio: LiveAudio, call: BridgeCall) -> None:
        while not call.closed.is_set():
            frame = await audio.frames.get()
            await call.send_audio(frame)

    async def _end(self, reason: str = "operator_hangup") -> None:
        if self._call is None:
            say("No call in progress.")
            return
        if self._pump is not None:
            self._pump.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._pump
        await self._call.stop(reason)
        if self._audio is not None:
            self._audio.stop()
        # The agent records the outbound outcome itself, and the backend marks a job that ended
        # without one as failed, so the bridge does not set a status here.
        say("Call ended.")
        self._audio = self._call = self._pump = None
        self._job_id = None

    # --- commands ----------------------------------------------------------------------------

    async def _answer(self) -> None:
        number = await ask("Caller number (Enter to skip): ")
        await self._begin(CallRequest("inbound", number or None))

    async def _outbound(self) -> None:
        job = await self._next_job()
        if job is None:
            say("No outbound jobs are queued.")
            return
        say(f"Job {job['id']}: dial {job['phone']} and say: {job['message']}")
        if (await ask("Press Enter when they answer (or type x to cancel): ")).lower() == "x":
            return
        self._job_id = job["id"]
        await self._job_status("dialling")
        try:
            await self._begin(CallRequest("outbound", job["phone"], job["id"]))
        except BridgeError:
            await self._job_status("failed", "bridge could not start the call")
            self._job_id = None
            raise

    async def run(self) -> None:
        say(f"Carwash bridge ({self._s.audio_mode} mode) -> {self._s.ws_url}")
        say(HELP)
        while True:
            if self._call is not None and self._call.closed.is_set():
                say("The backend ended the call.")
                await self._end("remote_hangup")
            cmd = (await ask("> ")).lower()
            try:
                if cmd == "a" and self._call is None:
                    await self._answer()
                elif cmd == "o" and self._call is None:
                    await self._outbound()
                elif cmd == "e":
                    await self._end()
                elif cmd == "q":
                    await self._end()
                    return
                else:
                    say(HELP if self._call is None else "Call in progress. e = end call")
            except BridgeError as exc:
                say(str(exc))
            except OSError as exc:  # no microphone, device busy, and so on
                say(f"Audio problem: {exc}")


def show_devices() -> None:
    for line in list_devices():
        say(line)
