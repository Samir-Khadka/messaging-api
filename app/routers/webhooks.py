"""Inbound webhooks: delivery receipts + incoming messages.

No API key here — vendors call these. In production, verify signatures:
  * Twilio: X-Twilio-Signature (HMAC of the URL + params with auth token)
  * Meta: X-Hub-Signature-256 (HMAC-SHA256 of the raw body with the app
    secret) + the hub.verify_token handshake below.
Signature verification is intentionally left as a documented TODO in the
README rather than half-implemented: a wrong check would silently drop
real receipts. Until it lands, put webhooks behind a secret path or IP
allowlist at the proxy.
"""

from fastapi import APIRouter, Form, Request
from fastapi.responses import PlainTextResponse

router = APIRouter(tags=["webhooks"])


@router.post("/v1/webhooks/twilio")
async def twilio_webhook(request: Request, MessageSid: str = Form(default=""),
                         MessageStatus: str = Form(default=""),
                         From: str = Form(default=""),
                         Body: str = Form(default="")):
    db = request.app.state.db
    row = db.get_message_by_provider_id(MessageSid)
    if row and MessageStatus:
        db.update_message(row["id"], status=MessageStatus)
    elif Body:
        db.insert_inbound(from_phone=From or None, channel="sms",
                          provider="twilio", body=Body,
                          raw={"MessageSid": MessageSid})
    return PlainTextResponse("ok")


@router.get("/v1/webhooks/meta")
async def meta_verify(request: Request, hub_mode: str = "",
                      hub_verify_token: str = "",
                      hub_challenge: str = ""):
    """Meta's webhook handshake: echo the challenge when the token matches."""
    settings = request.app.state.settings
    if (hub_mode == "subscribe"
            and settings.meta_verify_token
            and hub_verify_token == settings.meta_verify_token):
        return PlainTextResponse(hub_challenge)
    return PlainTextResponse("forbidden", status_code=403)


@router.post("/v1/webhooks/meta")
async def meta_webhook(request: Request):
    payload = await request.json()
    db = request.app.state.db
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for msg in value.get("messages", []):
                text = (msg.get("text") or {}).get("body")
                db.insert_inbound(
                    from_phone=msg.get("from"), channel="whatsapp",
                    provider="meta", body=text, raw=msg)
            for st in value.get("statuses", []):
                row = db.get_message_by_provider_id(st.get("id", ""))
                if row and st.get("status"):
                    db.update_message(row["id"], status=st["status"])
    return {"ok": True}
