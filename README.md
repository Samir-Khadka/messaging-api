# Messaging API — SMS, WhatsApp, RCS, OTP in one API

One FastAPI service that sends messages on three channels and handles
OTP login codes, behind a single API-key-authenticated API. Providers are
pluggable: the default for every channel is a **console provider** that
records messages without sending them, so the whole API works with zero
credentials. Swap a channel to a real vendor when you have its keys.

## Quickstart

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
./run.sh            # http://localhost:8000, docs at /docs
```

Dev key (DEV_MODE=true): `dev-key-change-me`.

```bash
# Send an SMS (dev mode: recorded, status "logged")
curl -X POST localhost:8000/v1/messages \
  -H "X-API-Key: dev-key-change-me" \
  -H "Content-Type: application/json" \
  -d '{"to": "+9779862853613", "channel": "sms", "body": "Hello from the API"}'

# Send an OTP, then verify it (dev mode: read the code back)
curl -X POST localhost:8000/v1/otp/send \
  -H "X-API-Key: dev-key-change-me" \
  -d '{"phone": "+9779862853613"}'
curl "localhost:8000/v1/dev/otp-code?phone=%2B9779862853613" \
  -H "X-API-Key: dev-key-change-me"
curl -X POST localhost:8000/v1/otp/verify \
  -H "X-API-Key: dev-key-change-me" \
  -d '{"phone": "+9779862853613", "code": "123456"}'
```

## Endpoints

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/health` | Liveness, no auth |
| GET | `/v1/status` | Which provider serves each channel (no secrets) |
| POST | `/v1/messages` | Send on `sms`, `whatsapp`, or `rcs`. Optional `template_name`/`template_language` (WhatsApp), `media_url`, `fallback_channel` (e.g. `whatsapp` → `sms`). `Idempotency-Key` header replays the original response instead of resending. |
| GET | `/v1/messages/{id}` | One message + delivery state |
| GET | `/v1/messages?status=&channel=&limit=` | Message history |
| POST | `/v1/otp/send` | Send a 6-digit OTP on `sms` (default), `whatsapp`, or `rcs` |
| POST | `/v1/otp/verify` | Verify a code. Returns `{"verified": true/false, "reason": ...}` |
| GET | `/v1/dev/otp-code?phone=` | **DEV_MODE only.** Read back the active code for testing |
| POST | `/v1/webhooks/twilio` | Twilio delivery receipts + inbound SMS |
| GET/POST | `/v1/webhooks/meta` | Meta webhook handshake + WhatsApp receipts/inbound |

## Providers

| Channel | Provider | Env | Notes |
| --- | --- | --- | --- |
| sms | `console` (default) | — | Recorded, status `logged` |
| sms | `twilio` | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_SMS_FROM` | Real SMS worldwide, incl. Nepal numbers |
| whatsapp | `console` (default) | — | Recorded, status `logged` |
| whatsapp | `twilio` | `TWILIO_WHATSAPP_FROM` | Free-form text only, inside the 24-hour customer-service window |
| whatsapp | `meta` | `META_ACCESS_TOKEN`, `META_PHONE_NUMBER_ID` | Text, images, and **approved templates** — the right choice for business-initiated messages (OTP, notifications) |
| rcs | `console` (default) | — | Recorded, status `logged` |
| rcs | `rcs` | `RCS_PROVIDER_URL`, `RCS_PROVIDER_TOKEN` | Generic HTTP adapter for an RBM-compatible endpoint |

### WhatsApp rules that will bite you if ignored

- **Templates:** outside the 24-hour window (user messaged you first),
  Meta only delivers approved templates. Pass `template_name` and
  `template_language` (e.g. `en_US`); the OTP body becomes the
  template's `{{1}}` parameter when the template has one.
- **Opt-in:** recipients must have agreed to receive WhatsApp messages
  from your business number. Never import a phone list and blast it.
- **Twilio vs Meta:** Twilio is simpler for two-way chat; Meta is the
  correct provider for template notifications and OTP at scale.

### RCS, stated honestly

Real RCS delivery runs through Google RCS Business Messaging (RBM) and
requires a registered, verified RBM agent plus a partner endpoint —
there is no public "just send RCS" API. This service's `rcs` provider is
a thin adapter over an RBM-compatible endpoint you configure; without
one, RCS stays on `console` and the API says the message was logged,
not sent. If your RBM partner's request shape differs, edit
`app/providers/rcs.py` — nothing else changes.

## OTP security

- Codes are 6 digits from `secrets`, 10-minute expiry, 5 attempts max.
- Only an HMAC-SHA256 hash is stored. The plaintext code is stored
  **only** when `DEV_MODE=true` (the `dev_code` column) so local tests
  work; in production the code exists nowhere after sending.
- One active code per phone; a new send supersedes the old one.
- 60-second resend cooldown + 5 sends/hour per phone.
- Verify never echoes the code, and a used/expired/locked code stays dead.

## Using it from Kishan-Bazzar (or any app)

```python
import httpx

API = "http://localhost:8000"
KEY = {"X-API-Key": "your-key"}

# Replace demo-mode OTP with a real send:
httpx.post(f"{API}/v1/otp/send", headers=KEY,
           json={"phone": "+97798XXXXXXXX", "channel": "sms"})
ok = httpx.post(f"{API}/v1/otp/verify", headers=KEY,
                json={"phone": "+97798XXXXXXXX",
                      "code": user_typed_code}).json()["verified"]

# Order update on WhatsApp, falling back to SMS:
httpx.post(f"{API}/v1/messages", headers=KEY, json={
    "to": "+97798XXXXXXXX", "channel": "whatsapp",
    "body": "Your order is on its way.",
    "fallback_channel": "sms",
})
```

## Production checklist

- [ ] `DEV_MODE=false` (disables the dev key and `/v1/dev/otp-code`)
- [ ] `MESSAGING_API_KEYS` = long random keys, `OTP_PEPPER` = long random value
- [ ] HTTPS in front (reverse proxy) — API keys in headers are not safe over HTTP
- [ ] Webhook signature verification (Twilio `X-Twilio-Signature`, Meta
      `X-Hub-Signature-256`) — see the TODO in `app/routers/webhooks.py`.
      Until it lands, restrict webhook paths by IP allowlist at the proxy.
- [ ] Message bodies are stored in SQLite for auditing. If you store
      regulated content, encrypt the body column at rest.
- [ ] Scale-out later: Postgres for storage, Redis for rate limits.

## Project layout

```
app/
  config.py            env-driven settings (no hardcoded secrets)
  db.py                SQLite: messages, otp_codes, inbound, idempotency
  security.py          X-API-Key auth, E.164 validation, rate limiter
  providers/           console, twilio, meta, rcs + registry
  services/            messaging.py (send + fallback), otp.py (lifecycle)
  routers/             messages.py, otp.py, webhooks.py
  main.py              FastAPI app + lifespan wiring
tests/                 pytest suite (auth, messages, OTP, webhooks)
```

## Tests

```bash
.venv/bin/python -m pytest tests/ -q
```
