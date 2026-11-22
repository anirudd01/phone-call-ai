# CPaaS research: Exotel vs Plivo for an Indian car-wash voice agent

Date of research: 2026-11-22 (every "checked" date below is this date unless stated).
Scope: inbound calls, outbound update calls, recording, Pipecat 1.16.0 + OpenAI Realtime, Railway wss endpoint, Indian small-business buyer.

Legend used throughout:
- **[V]** verified from a fetched or searched source (URL given), checked 2026-11-22.
- **[I]** inferred by me from sources; not stated outright.
- **[N]** not published or not found; do not rely on any number.
- Many pages were read through a summarising fetch tool, not the raw page. Treat exact figures as "as reported by the page summary" and re-confirm on the live page before paying.
- This is not legal advice. TRAI and DPDP points must be confirmed by counsel or the regulator text.

---

## 0. Executive summary

- Both providers can do what is needed: inbound number to your wss endpoint, outbound API call to your wss endpoint, both with two-way audio, and Pipecat has a built-in serializer for each.
- **Plivo** is published, self-serve and cheap: India outbound and inbound both Rs 0.38 per minute, number Rs 200 per month, audio streaming included, recording free. Its KYC accepts a GST certificate, Certificate of Incorporation or Udyam certificate. A landline number (080/022) is approved automatically in about 5 minutes. Its weakness: Indian numbers need an India-registered business and an India-region account; an individual with no business registration is not clearly eligible.
- **Exotel** is India-native with a Mumbai API cluster, but pricing is quote-based, the voice streaming feature is a separate paid add-on that must be enabled by Exotel, and the smallest published plan is Rs 9,999. Its KYC explicitly describes sole proprietors. It is the better fit if the owner is a sole proprietor without GST or wants local sales/support.
- Recommendation: start with **Plivo** (fastest, cheapest, documented) if the business has GST, Udyam or an incorporation certificate. Choose **Exotel** if it does not, or if Plivo support/latency disappoints in a test. Details in section 11.

---

## 1. Getting an Indian number

### 1.1 Plivo

| Item | Finding | Tag | Source (checked 2026-11-22) |
|---|---|---|---|
| Eligible customer | Only businesses registered in India can rent Indian numbers or use domestic routes; others get international routes only | V | https://www.plivo.com/docs/voice/concepts/india-calling.md |
| Account region | Indian numbers need an India data-region account; region cannot be changed after sign-up; India-issued card needed for India region; need India and international calling means two accounts | V | https://www.plivo.com/docs/voice/concepts/india-calling.md , search result summary of https://www.plivo.com/docs/faq/account/account-management |
| Number types | Landline (022, 080 etc.): non-BFSI service/transactional calls. 140 series: promotional only, extra setup. 160 series: BFSI only, extra setup. | V | https://docs.plivo.com/docs/numbers/rent-india-numbers.md |
| Mobile (+91 9/8/7/6) or toll-free DIDs | Not listed in the India number guide I could read; the pricing page mentions "Domestic numbers" only | N | pricing page https://www.plivo.com/voice/pricing/in/ |
| KYC documents | Submit any one: GST certificate (active GSTIN), Certificate of Incorporation (CIN), Udyam registration certificate. Business PAN alone not accepted. 140/160 series need additional documents (not listed). | V | https://docs.plivo.com/docs/numbers/rent-india-numbers.md |
| Conflicting report | A search summary of another Plivo page said COI and GST certificate are both needed and that KYC is signed/sealed on first application. The primary guide says any one document. Re-check in the console. | V (conflict) | search result for Plivo KYC, 2026-11-22 |
| Signed application | First application must be sealed and signed; Plivo verifies against government records; cancelled/suspended registrations are rejected | V | https://docs.plivo.com/docs/numbers/rent-india-numbers.md |
| Activation time | 080/022: review automated, "typically within 5 minutes". 140/160: separate SLA, not stated. | V | same |
| Individual / sole proprietor | The guide does not address individuals. Udyam can be held by a proprietorship, so a sole proprietor with Udyam may qualify. Plain individual without any of the three documents: not accepted per the document list. | V + I | same |
| GST | Not strictly required if you hold COI or Udyam; GST details optional or can be self-declared unregistered per older support articles | V (older) | https://old-support.plivo.com/hc/en-us/articles/36749835402905 (title seen in search only; body not read) |
| Trial | Trial account gives one free number in your sign-up country and requires verified "sandbox" destination numbers. Free credit amount not found. Trial needs work email (personal domains rejected) and a non-VoIP SMS-capable phone. | V (credit amount N) | search summary, https://www.plivo.com/docs/faq/account/account-management ; https://www.plivo.com/pricing/ |
| Trial can place India calls? | Not confirmed whether a trial India-region account can rent an Indian landline before KYC | N | |

### 1.2 Exotel

| Item | Finding | Tag | Source |
|---|---|---|---|
| Number brand | Numbers are called ExoPhones, virtual numbers leased on licensed Indian operator networks | V | https://exotel.com/blog/voice-call-api-in-india/ |
| DID types (landline, mobile, toll-free) | Page does not list types. Toll-free is reported to have higher activation fee and per-minute inbound charges (third-party/aggregated search summary). | N / V weak | search summary 2026-11-22 |
| KYC | Required before buying ExoPhones or going live. Without approved KYC you can explore the dashboard and use trial credits only. Trial accounts lack production virtual numbers. | V | https://developer.exotel.com/docs/getting-started/kyc-verification , https://developer.exotel.com/docs/faqs/account-setup |
| KYC review time | Typically 2-3 business days after complete documents; blurry uploads cause delay | V | https://developer.exotel.com/docs/faqs/account-setup |
| Time from KYC approval to number | Not published | N | |
| Sole proprietor documents | Sources reported: PAN, proprietor ID proof, GST certificate or Shop and Establishment licence. GST not strictly mandatory if another business proof is supplied. Exact rule must be checked on the upload form. | V (summarised) | https://developer.exotel.com/docs/getting-started/kyc-verification , https://docs.exotel.com/business-phone-system/kyc-verification-indian-accounts |
| Voice streaming enablement | The Voicebot/Stream applet and Connect Voice AI API "may not be enabled on every account"; contact Exotel / hello@exotel.com | V | https://support.exotel.com/support/solutions/articles/3000108630-working-with-the-stream-and-voicebot-applet , https://docs.exotel.com/exotel-agentstream/connect-voice-ai-api |
| Trial | 7 days with Rs 500 credits (marketing page) | V | https://exotel.com/pricing/business-phone-system/ |
| Startup program | "Exotel for Startups" Rs 6,000 including free call/SMS credits for six months, a virtual landline, two licences; a separate page lists USD 2,000 telephony credits | V (page), eligibility N | same; https://www.getaiperks.com/en/ai/exotel-startup-program (third party) |
| Number series 140/160 | Not discussed on pages I read | N | |

---

## 2. Inbound call flow and audio streaming

### 2.1 Plivo

How a call reaches our server [V]: customer dials the Plivo number; the number is attached to a Plivo Application whose Answer URL (HTTP, ours) returns XML. The XML contains a `<Stream>` element whose body is our `wss://` URL. Plivo then opens the websocket. Source: https://docs.plivo.com/docs/voice-agents/audio-streaming/concepts/audio-streaming-reference.md and https://plivo.com/docs/voice-agents/audio-streaming/integration-guides/pipecat/overview (Answer URL setup applies to inbound).

Stream XML [V]:
```xml
<Response>
  <Stream bidirectional="true" keepCallAlive="true"
          contentType="audio/x-mulaw;rate=8000"
          extraHeaders="agentType=sales;language=kn">
    wss://your-app.up.railway.app/ws
  </Stream>
</Response>
```
- `bidirectional="true"` allows us to send audio back. `keepCallAlive="true"` is recommended for AI agents so the call stays up (https://www.plivo.com/docs/voice-agents/audio-streaming/overview.md). Without it, the call may continue to the next XML element when the stream ends [I].
- Full attribute list not published on the pages read [N]; there is also a `statusCallbackUrl` (events started, stopped, failed).

Audio [V]: `audio/x-mulaw;rate=8000` (recommended, lowest latency) or `audio/x-l16;rate=16000` (linear 16-bit PCM). Media is base64; chunks about 20 ms (about 160 bytes at 8 kHz mulaw).

Messages Plivo to us [V]:
- `start`: `event`, `sequenceNumber`, `start{callId, streamId, accountId, tracks, mediaFormat{encoding, sampleRate}}`, `extra_headers`
- `media`: `event`, `sequenceNumber`, `streamId`, `media{track, timestamp, chunk, payload}`, `extra_headers`
- `dtmf`: `dtmf{track, digit, timestamp}`
- `playedStream` (after a checkpoint), `clearedAudio`
- No `stop` websocket event is documented; stop is shown only as the HTTP status callback `stopped` [V]. In practice the socket closes [I].

Messages us to Plivo [V]: `playAudio` {`media{contentType, sampleRate, payload}`} (must match the Stream XML), `checkpoint` {streamId, name}, `clearAudio` {streamId}, `sendDTMF`.

Custom parameters [V]: `extraHeaders` attribute, semicolon-separated key=value pairs; they come back in `extra_headers` on events. Size limits not published [N].

Authentication and signing [V]: webhook (Answer URL) requests carry `x-plivo-signature-v3` and `x-plivo-signature-v3-nonce`; base string is method + full URI + nonce; HMAC-SHA256 with the Auth Token, base64, compare in constant time. Authentication for the websocket itself is not documented; use a secret token in the wss path or in `extraHeaders` [I]. Plivo outbound IP ranges for allow-listing: not found [N].

Stop/hang up [N for docs]: the audio-streaming pages I read do not cover hanging up. Pipecat's serializer hangs up via REST `DELETE /v1/Account/{auth_id}/Call/{call_id}/` (read from installed source).

### 2.2 Exotel

How a call reaches our server [V]: customer dials the ExoPhone; the number is assigned to an App Bazaar flow; flow = Call Start, Voicebot applet (URL = our wss), Hangup applet. Sources: https://developer.exotel.com/docs/agentstream/stream-voicebot-applet (same content fetched from https://support.exotel.com/support/solutions/articles/3000108630-working-with-the-stream-and-voicebot-applet) and https://docs.pipecat.ai/pipecat/telephony/exotel-websockets.md .

Applet differences [V]: Stream applet is one-way (transcription); **Voicebot applet is bidirectional**. Voicebot URL can be a static wss URL, or an https URL that returns JSON `{"url": "wss://..."}` (dynamic, lets us choose per call).

Audio [V]: raw signed linear PCM, 16-bit, mono, little-endian, base64. Sample rate 8 kHz default; 16 kHz and 24 kHz selectable with `?sample-rate=16000` on the URL. The page itself is inconsistent (protocol section says 8 kHz raw PCM); read `media_format` in the `start` message to be sure.
Bidirectional chunk rules [V]: minimum 3.2 KB (100 ms), maximum 100 KB, preferably multiples of 320 bytes; smaller chunks risk jitter issues, non-multiples create gaps.

Messages Exotel to us [V]: `connected`; `start` (`stream_sid`, `call_sid`, `account_sid`, `from`, `to`, `custom_parameters`, `media_format{encoding, sample_rate, bit_rate}`); `media` (`sequence_number`, `stream_sid`, `media{chunk, timestamp, payload}`); `dtmf` (`duration`, `digit`); `mark`; `stop` (`call_sid`, `account_sid`, `reason`).
Messages us to Exotel [V]: `media` (same shape), `mark`, `clear` (drop unplayed audio).

Custom parameters [V]: maximum 3, as query-string key-values on the URL, combined at most 256 characters, delivered in `start.custom_parameters`. Pipecat's guide warns query parameters may be stripped on dial-out and calls this an ongoing issue; workarounds: different endpoints or flows per scenario, or branch on the called number (https://docs.pipecat.ai/pipecat/telephony/exotel-websockets.md). Note the Exotel Connect Voice AI API doc says `StreamUrl` query string is delivered as `start.custom_parameters` (https://docs.exotel.com/exotel-agentstream/connect-voice-ai-api). The two sources conflict; test it [I].

Authentication [V]: IP allow-listing of Exotel outbound ranges (ask Exotel for the list) or Basic auth placed in the wss URL (sent as an Authorization header). No HMAC signing of websockets described [N].

Start/stop [V]: stream closes when the call disconnects, the socket closes, or before the next applet. The bot ends the call by closing the websocket (per the Connect Voice AI API doc); the inbound-flow doc does not describe a bot-initiated hangup; a Hangup applet after the Voicebot applet ends the call when the socket closes [I].

---

## 3. Outbound calls and Indian regulation

### 3.1 API to place a call

**Plivo** [V]: `POST https://api.plivo.com/v1/Account/{auth_id}/Call/` with Basic auth `auth_id:auth_token`; required `from` (our Plivo number), `to` (E.164), `answer_url` (our endpoint returning the `<Stream>` XML). Source: https://www.plivo.com/docs/voice-agents/audio-streaming/api/audio-streams.md (as summarised). Pipecat example: `plivo-chatbot/outbound` in the pipecat-examples repo (not read by me). Python SDK `plivo` exists [I].

**Exotel** [V]: `POST /v1/Accounts/{AccountSid}/Calls/connect`, Basic auth API key:token. Base `https://api.in.exotel.com` (Mumbai) or `https://api.exotel.com` (Singapore). Two styles:
1. Voice AI API (https://docs.exotel.com/exotel-agentstream/connect-voice-ai-api): `From` (customer number, international format), `CallerId` (our ExoPhone), `StreamUrl` (ws/wss, max 600 chars incl. query), `StreamType=bidirectional`, optional `Record`, `RecordingChannels` (single|dual), `TimeLimit` (max 14,400 s), `CustomField` (max 128 chars; only returned in status webhooks, not sent to the bot), `StatusCallback`, `StatusCallbackEvents[]`, `StreamName`. Needs the feature enabled on the account.
2. Flow style: `Url=http://my.exotel.com/{sid}/exoml/start_voice/{app_id}` where the app contains the Voicebot applet (https://docs.exotel.com/voice-apis/outbound-call-to-connect-a-customer-to-an-app ). `StatusCallbackEvents` returns 400 with a flow URL.
Naming warning: in Exotel's API `From` is the person called, `CallerId` is our number.

### 3.2 Caller ID

- Plivo: must be a Plivo-rented Indian number; arbitrary caller IDs not allowed [V] https://www.plivo.com/docs/voice/concepts/india-calling.md
- Exotel: "the CallerId must be an ExoPhone" [V] https://exotel.com/blog/voice-call-api-in-india/

### 3.3 TRAI rules (as stated by providers; primary TRAI text not read)

| Topic | Finding | Tag | Source |
|---|---|---|---|
| DLT | TCCCPR-2018: no entity not registered on DLT may send commercial communication by voice or SMS | V (search quote of TRAI guidance) | search result, TRAI/vendor guidance; https://developer.exotel.com/docs/faqs/tcccpr-2018 |
| DLT for pure voice service calls | Exotel says voice flows trigger DLT once you add an SMS follow-up or OTP fallback; whether a landline-series service voice call to existing customers needs DLT entity registration at Plivo/Exotel is not stated | N | https://exotel.com/blog/voice-call-api-in-india/ |
| DND / NDNC | Promotional calls to DND numbers blocked; transactional and service calls (order updates, service calls to existing customers) are allowed; DND changes take effect within 7 days | V | https://exotel.com/blog/voice-call-api-in-india/ |
| Message categories | Transactional (implied consent), Service-implicit (updates to existing customers, consent implied by relationship, no time limit), Service-explicit (opt-in), Promotional (opt-in, 9 AM-9 PM IST) | V (SMS-centred page; "does not describe separate rules for service voice calls") | https://developer.exotel.com/docs/faqs/tcccpr-2018 |
| Calling hours | Promotional restricted to 9 AM-9 PM IST; transactional/service "None (24/7)" per Exotel FAQ. Primary regulation wording not verified. | V (vendor), primary N | same |
| Number series | 140: promotional voice only. Landline series (022, 080...): service/transactional only (Plivo, non-BFSI). 160: service/transactional, BFSI only. Using the wrong series is a violation; complaints are treated as UCC regardless of consent. | V | https://www.plivo.com/docs/voice/concepts/india-calling.md , https://docs.plivo.com/docs/numbers/rent-india-numbers.md |
| Newer numbering | A 2026 TRAI release refers to 1600xx series for service/transactional calls; I did not read it | V weak | search result TRAI PR 119 of 2026: https://www.trai.gov.in/sites/default/files/2026-09/PR_No119of2026.pdf |
| Cold calling | "Prohibited in India"; commercial calls need explicit digital consent; no valid consent = UCC | V | https://www.plivo.com/docs/voice/concepts/india-calling.md |
| Service/transactional exemption | Service calls generally do not need explicit consent; transaction alerts within 30 minutes of a customer's transaction need none | V | same |
| No mixing | No promotional/upsell/cross-sell content on transactional or service calls | V (search quote of TRAI guidance) | search result |
| Penalties | Up to Rs 1,000 per call/day for UCC to DND numbers; 7+ complaints in a month: disconnection of telecom resources up to 2 years | V (Exotel FAQ) | https://developer.exotel.com/docs/faqs/tcccpr-2018 |
| AI / robo calls | TRAI actions on AI-driven telemarketing exist (ssrana.in article); a CXOToday article refers to "A2P mandates for AI voice infrastructure". Contents not read, so no specific rule can be stated. | N | https://ssrana.in/articles/trais-crackdown-on-spam-calls-and-ai-driven-telemarketing/ |

### 3.4 What a service update call to an existing customer needs [I, built from above]

Calls such as "your car is ready" to someone who has just done business with the shop are **service (implicit-consent) calls**, not promotional. Practical conditions inferred:
1. Place them from the provider's landline-series (080/022 style) number, not a 140 number, and never include offers or upsell in the call (the agent prompt must forbid promotion).
2. Keep a record of the customer's phone number as supplied by the customer and the transaction.
3. Honour "do not call me" requests quickly (Exotel FAQ says 7 days for opt-out).
4. Whether DLT entity/header registration is required for voice service calls with these providers, and whether the provider will ask for it, must be confirmed with each provider's support before go-live [N].
5. Sector exemptions (the 160 series is BFSI only), so a car-wash does not qualify.

---

## 4. Pricing (INR)

### 4.1 Plivo [V unless noted] https://www.plivo.com/voice/pricing/in/ (checked 2026-11-22)

| Item | Price |
|---|---|
| Outbound domestic (India) | Rs 0.38/min (a developer pricing page showed Rs 0.40; the dedicated India page is the more specific, use Rs 0.38 but confirm) |
| Inbound domestic | Rs 0.38/min |
| Domestic number rental | Rs 200/month (a developer page showed Rs 250/month; conflict) |
| Billing increment | "Pulse is 30 seconds" (the global page says 60 s; India page is the one used) |
| Audio streaming | Included, no separate charge |
| Recording | Free; storage free for 90 days; then USD 0.0004 per min per month |
| Minimum deposit / commitment | Not found [N] |
| Tax | GST 18% presumably extra [I]; not stated on the page |
| Trial credit | Amount not found [N] |

### 4.2 Exotel

| Item | Finding | Tag | Source |
|---|---|---|---|
| Plans (INR, validity) | Dabbler Rs 9,999 (rental Rs 4,999, credits 5,000, 5 months, 1 ExoPhone, 3 agents); Believer Rs 19,999 (rental Rs 10,499, credits 9,500, 11 months, 2 ExoPhones); Influencer Rs 49,499 (credits 39,000, 10 ExoPhones). 1 credit = Rs 1. | V | https://exotel.com/pricing/business-phone-system/ |
| Per-minute inbound / outbound | Not published on official pages | N | same |
| Voice streaming (Agent Stream) | "Available as a separate offering"; price not published; email hello@exotel.com or +91-808 8919 888 | V (no price) | same |
| Recording storage | Not published | N | |
| Taxes | 18% GST on all services (third-party summary) | V weak | search summary of https://www.cloudtalk.io/blog/exotel-pricing/ |
| Pricing model | Per pulse for voice; pulse length not seen; two-leg bridged calls cost both legs | V | https://developer.exotel.com/docs/billing/pricing-model (page itself 404 when fetched; seen in search summary) |
| Third-party market range (not Exotel) | Outbound Rs 0.30-1.20/min, inbound Rs 0.50-1.50/min (Enablex, a competitor) | V weak | https://www.enablex.io/insights/cloud-telephony-solutions-in-india-voice-api-ip-voice-bot-platform/ (as returned by search) |

### 4.3 Monthly estimate: 300 calls x 3 minutes = 900 minutes

Assumption: 150 inbound + 150 outbound, 3 minutes each (6 pulses of 30 s at Plivo), 1 number. Answered-call time only; unanswered outbound attempts ignored.

| Provider | Calculation | Estimate | Tag |
|---|---|---|---|
| Plivo | 900 min x Rs 0.38 = Rs 342; plus number Rs 200 = Rs 542; plus 18% GST = about Rs 640 per month | about Rs 640 | I on GST; rates V |
| Exotel | Cannot be computed: rates and streaming add-on unpublished. The cheapest published plan is Rs 9,999 for 5 months (about Rs 2,000 per month of validity) before streaming add-on and before usage; even that plan excludes streaming. | at least about Rs 2,000 per month plus unknown streaming fee [I] | N for real figure |

Not included for either: OpenAI Realtime cost (the dominant cost; not part of this research), Railway hosting.

---

## 5. Call recording and consent

Provider-side recording:
- Plivo [V]: recording free, stored free 90 days, then USD 0.0004/min/month (https://www.plivo.com/voice/pricing/in/). The mechanism for a streamed call (the `<Record>` element or the Record API) was not verified [N]; recording a call that is being streamed via XML may need `<Record>` before/alongside `<Stream>` or the Record API [I].
- Exotel [V]: voicebot applet has a Record checkbox giving a recording URL in the next passthru applet; Connect Voice AI API takes `Record` and `RecordingChannels=single|dual` and returns `RecordingUrl`. Retention and storage price not published [N].

Our-side recording [I]: our server sees both directions in the Pipecat pipeline (caller audio in; agent audio out), so we can record with Pipecat's `AudioBufferProcessor` into our own storage. This avoids provider storage fees and gives a time-aligned dual track, but costs our storage and compute, and must comply with the same consent rules. Not verified against Pipecat docs in this report.

Consent in India [mostly N/I]:
- I found **no statute or regulator text requiring a specific wording** such as "this call is being recorded" [N].
- Vendor and legal commentary says voice recordings are personal data under the DPDP Act 2023 and consent must be free, specific, informed, unconditional, unambiguous, with separate consent per purpose (secondary sources: https://www.livelaw.in/articles/dpdpa-says-about-call-centre-data-548760 , https://edesy.in/blog/dpdp-act-voice-ai-compliance-india-2026.md , https://exotel.com/glossary/call-recording-compliance-in-india/). A vendor cites 13 May 2027 for full compliance; unverified.
- Recommendation [I]: play or speak an opening notice ("This call is handled by an automated assistant and may be recorded to improve service") at the start of every call, inbound and outbound, and offer a way to decline recording. Disclosing that the caller is speaking with an AI is advisable though no rule was verified [N].

---

## 6. Latency and quality

| Topic | Plivo | Exotel |
|---|---|---|
| India media region | Routes via nearest edge; India data-region account; both legs must stay in India ("media anchoring"; violating = `violates_media_anchoring` hangup) [V] https://www.plivo.com/docs/voice/concepts/india-calling.md | Mumbai API cluster `api.in.exotel.com` exists [V]; media region/data centre not stated [N] |
| Published latency targets | Under 1 s end to end target; network under 100 ms, STT 200 ms, LLM 500 ms, TTS 200 ms; mulaw 8 kHz lowest latency [V] https://www.plivo.com/docs/voice-agents/audio-streaming/overview.md . These are guidance, not measured Indian figures. | None; Exotel's Pipecat guide suggests buffering 200-300 ms of frames [V] https://exotel.com/blog/exotel-pipecat-agentstream-guide/ |
| Jitter / chunking | Chunks 20 ms | Minimum 100 ms outbound chunks recommended; smaller risks jitter [V] |
| Concurrency / WebSocket limits | Not published [N] | Not published [N] |
| Known complaints | None verified | None verified |

Hosting note [I]: Railway region should be as close to India as possible (Singapore is likely nearest) because the websocket hop adds latency both ways; the OpenAI Realtime link adds more. Not benchmarked.

Codec note [I]: both carry 8 kHz telephone audio (Plivo mulaw 8 kHz, Exotel PCM 8 kHz default). Kannada ASR quality on 8 kHz narrowband is a model risk independent of provider. Exotel offers 16 kHz/24 kHz, which may help recognition [I]; Plivo offers 16 kHz L16 as well [V] but Pipecat's Plivo serializer only emits mulaw (see section 8).

---

## 7. Developer experience

| Topic | Plivo | Exotel |
|---|---|---|
| Docs | Public, markdown-indexed, audio-streaming reference with message schemas [V]; some pages 404 or move (docs.plivo.com vs plivo.com/docs, "voice-agents" section new) [V observed] | Docs split between developer.exotel.com, docs.exotel.com and support.exotel.com; some pages 404 on fetch [V observed]; streaming doc is clear on message formats but vague on hangup and sample rate |
| Python | Official `plivo` SDK [I]; Pipecat guide and example [V] https://docs.pipecat.ai/pipecat/telephony/plivo-websockets.md | Plain REST (requests/httpx) [I]; Pipecat guide, inbound and outbound examples `exotel-chatbot` [V] https://docs.pipecat.ai/pipecat/telephony/exotel-websockets.md ; Exotel guide https://exotel.com/blog/exotel-pipecat-agentstream-guide/ ; Sarvam integration https://docs.sarvam.ai/api/integration/build-voice-agent-with-exotel |
| Testing without number | Trial account with sandbox destination numbers; ngrok for local [V] | 7-day trial with Rs 500; a stream simulator and echo-bot repos (`exotel/Agent-Stream`, `exotel/Agent-Stream-echobot`) [V]; production numbers need KYC |
| Support responsiveness | Not verified [N] | Support doc says response times in working hours (page seen only in a search listing: https://support.exotel.com/support/solutions/articles/3000068544); sales-led access to streaming [V] |
| Community complaints | Not verified [N] (a Trustpilot page exists, not read) | Not verified [N] |
| Terms on AI/automated calls | Not found; Plivo markets audio streaming for AI voice agents [V]. Plivo Acceptable Use policy not read [N] | Exotel markets AgentStream for conversational AI [V]; Terms not read [N] |
| Indian rules on AI calls | See section 3.3; no verified AI-specific rule | same |

---

## 8. Pipecat 1.16.0 integration specifics (read from installed source)

Files read: `backend\.venv\Lib\site-packages\pipecat\serializers\exotel.py` and `plivo.py` [V, local source].

### 8.1 ExotelFrameSerializer
- Constructor: `ExotelFrameSerializer(stream_sid: str, call_sid: str | None = None, params=None)`. Only `stream_sid` is required; `call_sid` is stored but unused.
- No account SID, API key or token needed. No REST hang-up code: **it never ends the call**.
- Params: `audio_in_sample_rate=8000`, `audio_out_sample_rate=8000` (`exotel_sample_rate`, `sample_rate` deprecated).
- Inbound: handles `event == "media"` (base64 PCM, resampled) and `event == "dtmf"` (`dtmf.digit`). It ignores `connected`, `start`, `stop`, `mark`; we must read `start` ourselves (Pipecat's `parse_telephony_websocket` helper does this and yields `stream_id`, `call_id`, `account_sid`, `from`, `to`) [V from https://docs.pipecat.ai/pipecat/telephony/exotel-websockets.md].
- Outbound: `InterruptionFrame` becomes `{"event":"clear","stream_sid":...}`; audio becomes `{"event":"media","stream_sid":...,"media":{"payload":...}}`. It does not send `chunk`, `sequence_number` or `timestamp` fields (not shown in the Exotel format as required, but unverified) and does not use `mark`.
- Gap 1 [I]: Exotel recommends 100 ms (3.2 KB, multiples of 320 bytes) chunks; the serializer sends whatever frame sizes the output transport produces (Pipecat's default is typically 20 ms packets). May cause jitter or gaps; test, and if needed raise the transport audio output chunk size or buffer.
- Gap 2: no hang-up. Ending the call means closing the websocket (per Connect Voice AI API doc) or ending via a Hangup applet; confirm closing the FastAPI websocket from the pipeline's end-of-call terminates the phone call.
- Gap 3: the Pipecat guide's code and the older text sometimes use `stream_id`/`call_id`/`account_sid`; the installed signature is `stream_sid`/`call_sid` [V locally].
- Sample rate: for 16 kHz set `?sample-rate=16000` on the Exotel URL and `audio_in_sample_rate=audio_out_sample_rate=16000` in params [I; consistent with the Exotel doc].

### 8.2 PlivoFrameSerializer
- Constructor: `PlivoFrameSerializer(stream_id, call_id=None, auth_id=None, auth_token=None, params=None)`.
- `auto_hang_up` defaults to **True**; then `call_id`, `auth_id` and `auth_token` are all required or the constructor raises `ValueError`. Set `auto_hang_up=False` in `InputParams` to skip credentials (then the call is not ended by us).
- Hang-up: on `EndFrame` or `CancelFrame` (once) it calls `DELETE https://api.plivo.com/v1/Account/{auth_id}/Call/{call_id}/` with Basic auth; 204 = success, 404 = already ended; errors are only logged. Requires `aiohttp`.
- Params: `audio_in_sample_rate=8000`, `audio_out_sample_rate=8000`.
- Inbound: `media` event (base64 mulaw to PCM) and `dtmf`; other events ignored; parse `start` ourselves (`streamId`, `callId`).
- Outbound: audio becomes `{"event":"playAudio","media":{"contentType":"audio/x-mulaw","sampleRate":<audio_out_sample_rate>,"payload":...},"streamId":...}`; interruption becomes `{"event":"clearAudio","streamId":...}`.
- Gap 1: output is always mulaw. The Stream XML `contentType` must therefore be `audio/x-mulaw;rate=8000`, with the default 8000 rates. Setting 16000 would send mulaw labelled 16 kHz and break (Plivo says content type must match the XML) [I].
- Gap 2: it sends `contentType` as plain `audio/x-mulaw` without `;rate=8000`; Plivo's docs show `audio/x-mulaw;rate=8000`. Matching strictness is unverified; test early [I].
- Gap 3: `checkpoint`/`playedStream` unused; no signature validation (we must verify `x-plivo-signature-v3` on the Answer URL ourselves). The websocket carries no auth, so protect the endpoint with a secret.
- Credentials needed: `PLIVO_AUTH_ID`, `PLIVO_AUTH_TOKEN` for outbound call creation and for hang-up.

### 8.3 Common to both
- Use `FastAPIWebsocketTransport` with `add_wav_header=False` and `serializer=...`; set `PipelineParams(audio_in_sample_rate=8000, audio_out_sample_rate=8000)` [V from Pipecat Exotel guide; same pattern for Plivo].
- OpenAI Realtime wants 24 kHz PCM; Pipecat resamples [I]. For telephone audio the model sees an 8 kHz-sourced signal.
- Pipecat examples exist: `exotel-chatbot/inbound|outbound` and `plivo-chatbot/inbound|outbound` in the pipecat-examples repo (not opened) .

---

## 9. Alternatives (brief)

| Provider | Why not (as primary) | Tag |
|---|---|---|
| Twilio | Indian numbers are heavily restricted/regulated; India outbound listed at about USD 0.0699/min on its pricing page, many times Plivo's Rs 0.38 (about USD 0.0045 at ~Rs 84/USD, my conversion) | V (price) / I |
| Knowlarity | Indian cloud-telephony vendor aimed at contact centres/IVR, sales-led; I did not verify an open bidirectional websocket stream for developers | N |
| Ozonetel | Contact-centre platform (CloudAgent), sales-led; streaming for AI not verified | N |
| Vonage | India local number availability and KYC burden not researched; weak India presence | N |

I did not research Knowlarity, Ozonetel or Vonage docs; the reasons are positioning, not verified product limits.

---

## 10. Side-by-side comparison

| Dimension | Plivo | Exotel |
|---|---|---|
| Who can sign up | India-registered business with GST, COI or Udyam; India-region account; India card | India KYC; sole proprietor path documented (PAN, ID, GST or S&E licence) |
| Number types documented | Landline 080/022; 140; 160 (BFSI) | ExoPhone; types not listed |
| Number activation | 080/022 automated, about 5 min after KYC approved | KYC 2-3 business days; number time unknown |
| Streaming | Included, self-serve, documented | Separate paid offering, must be enabled by Exotel sales |
| Audio | mulaw 8 kHz or L16 16 kHz | PCM 16-bit 8/16/24 kHz |
| Inbound config | Application Answer URL returns `<Stream>` XML (dynamic per call) | App Bazaar flow with Voicebot applet; optional dynamic https URL |
| Outbound API | `Call` API with `answer_url` | `Calls/connect` with `StreamUrl` (needs feature enabled) |
| Custom params | `extraHeaders` | up to 3 query params, 256 chars; reliability on dial-out disputed |
| Webhook signing | HMAC-SHA256 v3 headers | None found; IP allow-list or Basic auth |
| Pipecat hang-up | Auto via REST (credentials needed) | None; close the socket |
| Recording | Free, 90 days free storage | Flag in API; price unpublished |
| Price (India) | Rs 0.38/min both ways, Rs 200/month number | Quote only; min plan Rs 9,999 |
| Est. 900 min/month | about Rs 640 incl. GST (inferred) | not computable; at least about Rs 2,000 (inferred) |
| India media region | Both legs must stay in India; edge routing | Mumbai API cluster; media region not stated |
| Support | Not verified | India-based, sales-led |

---

## 11. Recommendation

Recommend **Plivo**, conditional on the business holding at least one of: GST certificate, Udyam registration, or Certificate of Incorporation.

Reasons:
1. Everything needed is self-serve and published: streaming included in price, documented message formats, signed webhooks, free recording, automated landline number approval.
2. Costs are known and low (about Rs 640 a month for the stated load), against an Exotel price that requires a sales conversation and a likely Rs 9,999 plan.
3. The Pipecat serializer handles hang-up automatically, removing a failure mode.
4. The 080/022 landline series is exactly the series meant for service/transactional calls by a non-BFSI business, matching the car-wash update calls.

**Exotel wins if:**
- The owner is a sole proprietor with none of GST, Udyam or incorporation (Plivo's list excludes PAN alone; Exotel documents a proprietor path).
- Plivo cannot supply a number for the owner's city, or Plivo support/latency tests in India are poor.
- Local account management and Mumbai-region API are valued, or a mobile-number DID is required (not confirmed at Plivo).
- Quote for streaming comes in near Plivo's costs.

Hedge: because Pipecat supports both serializers, keep the provider behind a thin adapter (inbound handler plus outbound caller) so switching costs about a day [I].

---

## 12. Go-live checklist

1. Owner decides legal entity paperwork available (GST / Udyam / COI / PAN / ID). Obtain Udyam (free online) if none exists [I].
2. Create Plivo account in the **India data region** with a work email, Indian phone, Indian credit card.
3. Submit Plivo India KYC (any one of GST/COI/Udyam), sealed and signed first application; wait for Approved status.
4. Rent an 080/022 landline-series number (service/transactional). Do not buy a 140 number.
5. Ask Plivo support in writing: (a) is DLT entity registration needed for voice service calls, (b) is AI-agent usage allowed under their terms, (c) concurrency limit, (d) streaming inclusion for India confirmed, (e) mobile or toll-free availability.
6. Deploy the FastAPI app on Railway with a public `wss://` endpoint and an `https` Answer URL; store `PLIVO_AUTH_ID`, `PLIVO_AUTH_TOKEN` as Railway secrets (never in the repo).
7. Create a Plivo Application whose Answer URL returns `<Stream bidirectional="true" keepCallAlive="true" contentType="audio/x-mulaw;rate=8000">wss://...</Stream>`; attach it to the number. Validate `x-plivo-signature-v3` on that endpoint; put a secret in the wss path.
8. Wire Pipecat: parse `start` for `streamId`/`callId`, build `PlivoFrameSerializer` with credentials, 8 kHz rates, `FastAPIWebsocketTransport`.
9. Test inbound with a real phone call; measure latency, check clipped audio and barge-in (`clearAudio`).
10. Implement outbound: `POST Call/` with `from` = our number, `to` = customer, `answer_url` pointing to our handler; pass context (customer, job id) via `extraHeaders` or a server-side lookup keyed by call id.
11. Add opening announcement (automated assistant; recording notice) in English/Kannada/Hindi; decide recording method (Plivo free vs own).
12. Restrict outbound to service content only; log consent/relationship basis; add a "do not call again" flag; stay within 9 AM-9 PM IST by policy even though service calls are reportedly unrestricted.
13. Trial with a small number of real customers; monitor Plivo billing in 30-second pulses and OpenAI cost.
14. If Plivo is rejected: repeat with Exotel: account and KYC (2-3 business days), request voice streaming enablement, get the written price, create Voicebot flow, use the Pipecat Exotel guide.

---

## 13. Open questions for the business owner

1. Is the business a sole proprietorship, partnership or company? Which of GST, Udyam, COI, PAN, Shop and Establishment licence exist?
2. Is the GST registered, and is the billing address the same as the registration address?
3. Who is the authorised signatory for the KYC form, and can they sign and seal it?
4. Do customers expect to call a landline number (080/022 city code) rather than a mobile number? Which city's code?
5. Does the business have an Indian credit card for the India data region?
6. Will outbound calls be strictly service (job ready, delay, schedule) or will they ever include offers? (Offers change the regulatory category completely.)
7. Is a customer-supplied phone number recorded with an existing transaction for every outbound call?
8. Are recordings needed at all, and for how long?
9. Expected peak concurrent calls?
10. Is the owner comfortable disclosing that callers speak to an AI assistant?

---

## 14. Could not verify

- Plivo: mobile/toll-free Indian numbers; Plivo trial credit amount; whether India trial accounts can buy numbers before KYC; full Stream XML attribute list; websocket stop semantics; hang-up docs in streaming pages; concurrency and stream limits; support quality; terms on AI calls; GST treatment on the invoice; conflict between Rs 0.38/0.40 and Rs 200/250.
- Plivo KYC conflict: "any one document" (primary guide) vs "COI and GST" (search summary).
- Exotel: per-minute rates, streaming add-on price, recording storage price, number types and DID rental, time from KYC to number, pulse length, concurrency, media data-centre, bot-initiated hang-up message, whether custom parameters survive on dial-out, support SLA, terms on AI calls. Exotel pricing-model page returned 404.
- TRAI: primary regulation texts (TCCCPR 2018, 2024 directions, 2026 press releases) not read; calling-hours rule for voice service calls taken from a vendor FAQ; 140/160/1600 series current status; any rule on AI-generated voice calls; DLT requirement for pure voice service calls.
- DPDP and recording consent: no regulator-mandated wording found; commentary is from vendors/legal blogs.
- Twilio, Knowlarity, Ozonetel, Vonage: not researched in depth.
- Pipecat: example repos (`exotel-chatbot`, `plivo-chatbot`) not opened; whether closing the websocket ends an Exotel call, and the effect of 20 ms chunks on Exotel, were not tested.
- Real-world latency: no measured India numbers from either provider.

## Key source list (all checked 2026-11-22)
- https://docs.plivo.com/docs/numbers/rent-india-numbers.md
- https://www.plivo.com/docs/voice/concepts/india-calling.md
- https://www.plivo.com/voice/pricing/in/
- https://docs.plivo.com/docs/voice-agents/audio-streaming/concepts/audio-streaming-reference.md
- https://www.plivo.com/docs/voice-agents/audio-streaming/overview.md
- https://docs.pipecat.ai/pipecat/telephony/plivo-websockets.md
- https://developer.exotel.com/docs/agentstream/stream-voicebot-applet (via https://support.exotel.com/support/solutions/articles/3000108630-working-with-the-stream-and-voicebot-applet)
- https://docs.exotel.com/exotel-agentstream/connect-voice-ai-api
- https://exotel.com/pricing/business-phone-system/
- https://exotel.com/blog/voice-call-api-in-india/
- https://developer.exotel.com/docs/faqs/tcccpr-2018
- https://developer.exotel.com/docs/getting-started/kyc-verification
- https://developer.exotel.com/docs/faqs/account-setup
- https://docs.pipecat.ai/pipecat/telephony/exotel-websockets.md
- https://exotel.com/blog/exotel-pipecat-agentstream-guide/
- Local: backend\.venv\Lib\site-packages\pipecat\serializers\exotel.py and plivo.py
