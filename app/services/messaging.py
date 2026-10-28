"""Outbound send flow: validate -> record -> deliver -> update.

A message row is created BEFORE delivery so nothing is ever silently
lost: a crash mid-send leaves a "queued" row, not a missing message.
Optional fallback_channel retries once on a different channel (e.g.
WhatsApp down -> SMS) and the fallback is recorded on the row.
"""

from ..db import Database
from ..providers.base import BaseProvider, ProviderError
from ..security import normalize_phone


def send_message(db: Database, providers: dict[str, BaseProvider], *,
                 to: str, channel: str, body: str | None = None,
                 template_name: str | None = None,
                 template_language: str | None = None,
                 media_url: str | None = None,
                 fallback_channel: str | None = None) -> dict:
    phone = normalize_phone(to)
    if channel not in providers:
        raise ValueError(f"unknown channel '{channel}' (sms, whatsapp, rcs)")
    if not body and not template_name and not media_url:
        raise ValueError("message needs a body, a template, or a media_url")

    provider = providers[channel]
    row = db.insert_message(
        to_phone=phone, channel=channel, provider=provider.name,
        body=body, template_name=template_name,
        fallback_channel=fallback_channel)
    try:
        result = provider.send(
            to=phone, body=body or "", channel=channel,
            template_name=template_name,
            template_language=template_language, media_url=media_url)
        db.update_message(row["id"], status=result.status,
                          provider_message_id=result.provider_message_id)
    except ProviderError as exc:
        if fallback_channel and fallback_channel in providers:
            fb_provider = providers[fallback_channel]
            fb_row_note = f"primary {channel} failed: {exc}"
            try:
                result = fb_provider.send(
                    to=phone, body=body or "", channel=fallback_channel,
                    media_url=media_url)
                db.update_message(
                    row["id"], status=result.status,
                    provider_message_id=result.provider_message_id,
                    provider=fb_provider.name, error=fb_row_note)
            except ProviderError as fb_exc:
                db.update_message(row["id"], status="failed",
                                  error=f"{exc}; fallback failed: {fb_exc}")
        else:
            db.update_message(row["id"], status="failed", error=str(exc))
    return db.get_message(row["id"])


def public_message(row: dict) -> dict:
    """What the API returns for a message. Bodies are included: this is a
    messaging API and operators need to audit content. If you store
    regulated content, encrypt the body column at rest (see README)."""
    return {
        "id": row["id"],
        "to": row["to_phone"],
        "channel": row["channel"],
        "provider": row["provider"],
        "body": row["body"],
        "template_name": row["template_name"],
        "status": row["status"],
        "provider_message_id": row["provider_message_id"],
        "fallback_channel": row["fallback_channel"],
        "error": row["error"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
