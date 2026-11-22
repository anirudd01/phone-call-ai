# Bridge <-> backend wire protocol (v1)

**Local testing only.** This protocol exists for the laptop bridge in `local/bridge`. Its
backend side lives in `backend/src/carwash_voice/transports/local/` (`protocol.py`,
`serializer.py`, `endpoint.py`). Keep this document in sync with that code. The real phone
path (Exotel or Plivo) uses the provider's own media-stream protocol instead.

## Connection

- Endpoint: `ws(s)://<host>/ws/local-bridge`.
- Auth: header `Authorization: Bearer <BRIDGE_TOKEN>`. If it is missing or wrong, the
  server accepts the socket and immediately closes it with code **4401**. The token is
  never accepted in the URL.
- One WebSocket per call. The bridge opens it when the operator starts a call and closes it
  when the call ends.
- The first message must be a text `start` message within **5 seconds**, otherwise the
  server sends an `error` message and closes with code **4400**. The same happens for an
  invalid `start` or an unsupported `protocol` number.
- If the server has no voice provider configured it sends `error` and closes with **4503**.
- The endpoint is only registered when `ENABLE_LOCAL_BRIDGE=true`.

## Audio (binary frames, both directions)

PCM signed 16-bit little-endian, mono, **16 000 Hz**. The server sends 20 ms frames
(640 bytes); the bridge should send 20 ms frames too.

## Control messages (text frames, JSON)

| Direction | Message | Meaning |
|---|---|---|
| bridge -> backend | `{"type":"start","protocol":1,"call_id":"<uuid4>","direction":"inbound"\|"outbound","caller_number":"+91..."\|null,"outbound_job_id":<int>\|null,"bridge_id":"spare-laptop"}` | First message. Backend creates the call record and starts the pipeline. `outbound_job_id` is the integer id from the outbound-jobs API. |
| bridge -> backend | `{"type":"stop","reason":"operator_hangup"\|"remote_hangup"\|"error"}` | Call ended on the phone side. The reason becomes the call's `end_reason`. |
| bridge -> backend | `{"type":"mark","name":"..."}` | Optional debug marker, logged only. |
| backend -> bridge | `{"type":"ready","call_id":"..."}` | Pipeline is running; start sending audio. |
| backend -> bridge | `{"type":"clear"}` | Customer interrupted the agent: flush the playback buffer now. |
| backend -> bridge | `{"type":"end_call","reason":"..."}` | Agent finished. Tell the operator to hang up, then send `stop` and close. |
| backend -> bridge | `{"type":"error","message":"..."}` | Fatal problem; show it and close. |

## Call end reasons stored on the call record

`operator_hangup`, `remote_hangup`, `error` (from `stop`), `remote_hangup` (socket dropped
without `stop`), `max_duration` (`MAX_CALL_SECONDS` reached), or an agent-chosen reason from
the `end_call` tool.

Note: a `stop` message with an unknown reason string is stored as sent.
