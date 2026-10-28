"""Meta WhatsApp Cloud API adapter (WhatsApp only).

Supports free-form text AND approved templates. Templates are required
for business-initiated messages outside the 24-hour window — that is the
normal case for notifications and OTPs, so prefer this provider for
production WhatsApp.
"""

import json
import urllib.error
import urllib.request

from ..config import Settings
from .base import BaseProvider, ProviderError, SendResult


class MetaWhatsAppProvider(BaseProvider):
    name = "meta"

    def __init__(self, settings: Settings) -> None:
        if not settings.meta_access_token or not settings.meta_phone_number_id:
            raise ProviderError(
                "Meta selected but META_ACCESS_TOKEN / META_PHONE_NUMBER_ID"
                " are not set")
        self._token = settings.meta_access_token
        self._url = (
            f"https://graph.facebook.com/{settings.meta_api_version}/"
            f"{settings.meta_phone_number_id}/messages")

    def send(self, *, to: str, body: str, channel: str,
             template_name: str | None = None,
             template_language: str | None = None,
             media_url: str | None = None) -> SendResult:
        if channel != "whatsapp":
            raise ProviderError(f"Meta provider supports whatsapp only, not '{channel}'")
        if template_name:
            payload = {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "template",
                "template": {
                    "name": template_name,
                    "language": {"code": template_language or "en_US"},
                },
            }
            if body:
                # Body text becomes the first body parameter when the
                # template has a {{1}} placeholder; templates without
                # parameters ignore it.
                payload["template"]["components"] = [{
                    "type": "body",
                    "parameters": [{"type": "text", "text": body}],
                }]
        elif media_url:
            payload = {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "image",
                "image": {"link": media_url, "caption": body},
            }
        else:
            payload = {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "text",
                "text": {"preview_url": False, "body": body},
            }
        req = urllib.request.Request(
            self._url, data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {self._token}",
                     "Content-Type": "application/json"},
            method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            raise ProviderError(
                f"Meta rejected the message ({exc.code}): "
                f"{exc.read().decode(errors='replace')[:300]}")
        except OSError as exc:
            raise ProviderError(f"Meta request failed: {exc}")
        messages = result.get("messages") or []
        return SendResult(
            provider_message_id=messages[0].get("id", "") if messages else "",
            status="sent",
            raw=result,
        )
