"""Messaging API — one API for SMS, WhatsApp, RCS, and OTP.

Run:  ./run.sh            (or: .venv/bin/uvicorn app.main:app --port 8000)
Docs: http://localhost:8000/docs
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import Settings
from .db import Database
from .providers import build_providers
from .routers import messages, otp, webhooks
from .security import set_api_keys

log = logging.getLogger("messaging")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()
    app.state.settings = settings
    app.state.db = Database(settings.database_path)
    set_api_keys(settings.api_keys)
    try:
        app.state.providers = build_providers(settings)
    except Exception as exc:
        log.error("provider setup failed: %s", exc)
        raise
    if settings.dev_mode:
        log.warning("DEV_MODE is on: dev key active, /v1/dev/otp-code enabled."
                    " Do not use in production.")
    if settings.otp_pepper == "dev-pepper-change-me" and not settings.dev_mode:
        log.warning("OTP_PEPPER is the dev default — set a real one.")
    yield


app = FastAPI(
    title="Messaging API",
    description="One API for SMS, WhatsApp, RCS, and OTP — with pluggable"
                " providers. Default provider is console (dev): messages"
                " are recorded, not sent.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
def health():
    return {"ok": True}


app.include_router(messages.router)
app.include_router(otp.router)
app.include_router(webhooks.router)
