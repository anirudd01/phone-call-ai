# Task 0: Bluetooth hands-free feasibility test

**Local testing only.** This test answers one question: can the spare Windows laptop
(a) hear the remote caller and (b) send audio the caller hears, during a real SIM call,
using only Windows' own Bluetooth hands-free support? No Phone Link app, no root.

Run everything on the **spare laptop**, natively on Windows (not Docker, not WSL).

## Steps

1. **Install the tools** (no admin needed for uv):
   - Python 3.12 from python.org or the Microsoft Store.
   - `uv`: `py -3.12 -m pip install --user uv` (then use `py -3.12 -m uv ...` if `uv` is
     not found), or the official uv installer.
   - Clone the repo and open PowerShell in `local\spike`.
   - First run: `uv sync` (installs sounddevice and numpy).
2. **Keep Phone Link out of the way.** If Phone Link ("Link to Windows") is installed,
   sign out of it or turn off its calls feature, so it does not grab the call audio.
3. **Pair the phone** in Windows Settings, Bluetooth & devices. On the phone, open the
   paired device's settings and allow **Phone calls** (hands-free) for the laptop.
4. **Place a test call.** From another phone, call SIM 2 and answer it on the phone.
   Check the call audio moved to the laptop (on the phone's call screen, choose the laptop
   or Bluetooth as the audio output if needed). Windows should show a hands-free device.
5. **Run the scripts.**
   - Before the call: `uv run python list_devices.py`. Save the output.
   - During the call: `uv run python list_devices.py --name "<your phone name>"`.
     Note which devices appear only during the call (look for `<<<` marks).
   - Record the caller: `uv run python record_call.py --device "<phone name, e.g. Nord 6>" --seconds 15 --out caller.wav`
     (ask the caller to talk). Play `caller.wav` on the laptop and listen.
   - Play into the call: `uv run python play_into_call.py --device "<phone name, e.g. Nord 6>"`
     (three rising beeps; the caller should hear them). You can add `--wav prompt.wav`
     for a spoken clip (16-bit PCM WAV).
   - Loopback: `uv run python loopback_test.py --in-device "<phone name>" --out-device "<phone name>"`
     (the caller says something, then hears it back).
   - If the device name differs on your machine, use a different part of the name from
     `list_devices.py` (for example the phone's name).
6. **Fill in the result table** below (or send me the numbers and I will).

### Things to watch for

- **Use the phone's name, not just "Hands-Free".** Other Bluetooth devices (earbuds, a
  headset) also have "Hands-Free" entries, and the script may pick those. The phone's
  entries look like `Hands-Free HF Audio (<phone name>)`. On the first test the phone
  showed up only under the Windows WDM-KS host API at 8000 Hz, mono.
- **Error 0x48F / "Error starting stream"** means the chosen device is not connected.

- **Mic must be open first?** If the call audio only appears while some app holds the
  hands-free microphone open, say so. The bridge would then need to open the mic first to
  trigger the call-audio link.
- **Two entries per device?** Windows often lists the same device under several host
  APIs (MME, DirectSound, WASAPI). Prefer WASAPI. If the script says "No input device",
  try a shorter name fragment.
- **Silence?** `record_call.py` prints the signal level. Peak of `-inf` or below about
  -60 dBFS means no audio is arriving.
- **Admin prompts?** Note anything that asked for administrator rights.

## Results

| Check | Result |
|---|---|
| Input device name / host API / sample rate | |
| Output device name / host API / sample rate | |
| Bridge hears the caller clearly | |
| Caller hears bridge audio clearly | |
| Audio quality (8 kHz narrowband or 16 kHz wideband) | |
| Noticeable echo / delay | |
| Anything that needed admin rights | |

**Go / no-go:** _(fill in after the test)_

If it does not work, stop and decide with the project owner: move to an Indian CPaaS
(Exotel or Plivo; the backend tasks still apply, only the transport changes), or boot
Linux from a USB stick on the spare laptop and use BlueZ with PipeWire or oFono.
Docker and WSL cannot reach the laptop's Bluetooth.
