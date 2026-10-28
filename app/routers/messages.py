"""Message endpoints. All require X-API-Key."""

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from ..security import require_api_key
from ..services import messaging

router = APIRouter(tags=["messages"])


class SendMessageBody(BaseModel):
    to: str = Field(..., examples=["+9779862853613"])
    channel: str = Field(..., examples=["sms"],
                         description="sms | whatsapp | rcs")
    body: str | None = Field(default=None, examples=["Your order shipped."])
    template_name: str | None = Field(
        default=None,
        description="WhatsApp approved template (Meta provider). "
                    "Required for business-initiated WhatsApp outside the "
                    "24-hour window.")
    template_language: str | None = Field(default=None, examples=["en_US"])
    media_url: str | None = Field(default=None)
    fallback_channel: str | None = Field(
        default=None,
        description="If the primary channel fails, retry once here, "
                    "e.g. whatsapp -> sms.")


@router.post("/v1/messages", dependencies=[Depends(require_api_key)])
def send_message(payload: SendMessageBody, request: Request,
                 idempotency_key: str | None = Header(default=None)):
    db = request.app.state.db
    if idempotency_key:
        cached = db.get_idempotency(idempotency_key)
        if cached:
            return cached
    try:
        row = messaging.send_message(
            db, request.app.state.providers,
            to=payload.to, channel=payload.channel, body=payload.body,
            template_name=payload.template_name,
            template_language=payload.template_language,
            media_url=payload.media_url,
            fallback_channel=payload.fallback_channel)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    result = messaging.public_message(row)
    if idempotency_key:
        db.save_idempotency(idempotency_key, result)
    return result


@router.get("/v1/messages/{message_id}", dependencies=[Depends(require_api_key)])
def get_message(message_id: str, request: Request):
    row = request.app.state.db.get_message(message_id)
    if not row:
        raise HTTPException(status_code=404, detail="message not found")
    return messaging.public_message(row)


@router.get("/v1/messages", dependencies=[Depends(require_api_key)])
def list_messages(request: Request, status: str | None = None,
                  channel: str | None = None, limit: int = 50):
    rows = request.app.state.db.list_messages(
        status=status, channel=channel, limit=min(limit, 200))
    return {"messages": [messaging.public_message(r) for r in rows]}


@router.get("/v1/status", dependencies=[Depends(require_api_key)])
def status(request: Request):
    """Which provider serves each channel. No credentials are exposed."""
    settings = request.app.state.settings
    return {
        "dev_mode": settings.dev_mode,
        "providers": {
            "sms": settings.sms_provider,
            "whatsapp": settings.whatsapp_provider,
            "rcs": settings.rcs_provider,
        },
    }
