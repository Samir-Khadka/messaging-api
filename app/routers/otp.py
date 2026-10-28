"""OTP endpoints. All require X-API-Key.

The dev helper GET /v1/dev/otp-code exists ONLY when DEV_MODE=true and
is the one place a plaintext code can be read back. It must never be
enabled in production.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ..security import require_api_key
from ..services import otp as otp_service

router = APIRouter(tags=["otp"])


class OtpSendBody(BaseModel):
    phone: str = Field(..., examples=["+9779862853613"])
    channel: str = Field(default="sms", examples=["sms"])


class OtpVerifyBody(BaseModel):
    phone: str = Field(..., examples=["+9779862853613"])
    code: str = Field(..., examples=["123456"])


@router.post("/v1/otp/send", dependencies=[Depends(require_api_key)])
def send_otp(payload: OtpSendBody, request: Request):
    try:
        return otp_service.request_otp(
            request.app.state.db, request.app.state.providers,
            request.app.state.settings,
            phone=payload.phone, channel=payload.channel)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except otp_service.OtpRateLimited as exc:
        raise HTTPException(status_code=429, detail=str(exc))


@router.post("/v1/otp/verify", dependencies=[Depends(require_api_key)])
def verify_otp(payload: OtpVerifyBody, request: Request):
    try:
        ok, reason = otp_service.verify_otp(
            request.app.state.db, request.app.state.settings,
            phone=payload.phone, code=payload.code)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"verified": ok, "reason": reason}


@router.get("/v1/dev/otp-code", dependencies=[Depends(require_api_key)])
def dev_otp_code(request: Request, phone: str):
    """DEV ONLY. Returns the active plaintext code for a phone so local
    testing works without a real gateway."""
    settings = request.app.state.settings
    if not settings.dev_mode:
        raise HTTPException(status_code=404, detail="not found")
    code = request.app.state.db.get_dev_code(phone)
    if not code:
        raise HTTPException(status_code=404, detail="no active code")
    return {"phone": phone, "code": code}
