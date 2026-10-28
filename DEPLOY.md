# Deploying the Messaging API (Render, free tier)

`render.yaml` at the repo root is a Render Blueprint: dashboard →
New → Blueprint Instance → pick `Samir-Khadka/messaging-api` → it
creates the `messaging-api` web service on the free plan.

## What "real" needs, in order

1. **The service itself** — the Blueprint boots it with the console
   provider. It answers `/health` but sends nothing real yet.
2. **A real provider account (the only part needing Samir):**
   - **Twilio SMS (simplest real path):** free trial signup at
     twilio.com → verify one phone number → a trial number is issued.
     Trial limits that matter: messages go ONLY to verified numbers,
     and trial texts carry a trial notice. Real delivery to any farmer
     needs an upgraded (paid) account + a purchased number.
     Values needed: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`,
     `TWILIO_SMS_FROM` (the Twilio number, E.164).
   - **Meta WhatsApp (later):** needs a Meta developer app, a WhatsApp
     Business account, and approved message templates for
     business-initiated messages. More setup than Twilio SMS.
3. **Wire the secrets:** in the Render dashboard for `messaging-api`,
   set `SMS_PROVIDER=twilio`, the three `TWILIO_*` values,
   `MESSAGING_API_KEYS` (one long random key), `OTP_PEPPER` (long
   random value), and flip `DEV_MODE=false`. Redeploy.
4. **Point Kishan-Bazzar at it:** on the `kisan-bazar` Render service,
   set `KISAN_MESSAGING_API_URL` to the messaging-api URL and
   `KISAN_MESSAGING_API_KEY` to the same key from step 3. Redeploy.
   Kishan-Bazzar's `/v1/auth/request-code` then sends real SMS.
5. **Prove it:** request a code for your own number from the live
   Kishan-Bazzar app and confirm the text arrives.

## Free-tier facts (no surprises)

- The service sleeps when idle: the first request after idle can take
  30–60s (cold start). OTP sends still work; they are just slow once.
- The filesystem is ephemeral: the SQLite message log resets on
  redeploy/restart. OTP codes are short-lived, so nothing critical is
  lost — but treat the log as audit, not a permanent record.
- `DEV_MODE=true` must never stay on a public URL once real keys
  exist: it enables the dev API key and `/v1/dev/otp-code`.
