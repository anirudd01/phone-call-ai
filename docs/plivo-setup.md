# Plivo setup (inbound and outbound calls)

What the code already does: `POST /plivo/answer` checks Plivo's signature and replies with
`<Stream>` XML; Plivo then opens `wss://<host>/ws/plivo/<PLIVO_WS_SECRET>`, and the call runs
through the same voice agent as every other transport. Tested offline only; nothing here has
been tried against real Plivo yet.

## What you need to do (account side)

1. Create a Plivo account and complete India KYC with your Udyam certificate. Ask support
   whether a voice service line needs DLT entity registration (the research report could not
   confirm it).
2. Rent an Indian **landline-series** number (080 or similar). Do not use a 140 number, and keep
   offers out of calls.
3. Deploy the backend somewhere with a public https address (Railway, task 11), or use a tunnel
   such as ngrok for a first test.
4. Set these in the backend environment: `PUBLIC_BASE_URL` (for example
   `https://carwash.up.railway.app`, no trailing slash), `PLIVO_AUTH_ID`, `PLIVO_AUTH_TOKEN`,
   `PLIVO_WS_SECRET` (a long random string), `PLIVO_NUMBER`.
5. In the Plivo console create an Application with Answer URL
   `<PUBLIC_BASE_URL>/plivo/answer`, method POST, and attach your number to it.
6. Ring the number from another phone.

## Notes

- The agent hangs up by the Plivo serializer calling Plivo's hang-up API when the call ends.
- The media format is 8 kHz mu-law, which is what Pipecat's Plivo serializer sends.
- Outbound calls: still to do (task 9). The answer URL already understands `?job_id=<id>`.
