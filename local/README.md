# local/ : local testing tooling only

This folder holds the Bluetooth bridge: spike scripts (`spike/`), the Windows bridge app
(`bridge/`) and its docs (`docs/`). It lets a stock Android phone act as the phone line by
pairing with a spare Windows laptop as a hands-free device.

It is **throwaway test tooling** for checking the phone flow and getting a feel for the
agent. The real, long-term call path is a CPaaS transport (Exotel or Plivo) inside the
normal backend structure. Nothing outside `local/` and `backend/src/carwash_voice/transports/local/`
may import from these, so both can be deleted later.

Start with [docs/spike-bluetooth.md](docs/spike-bluetooth.md).
