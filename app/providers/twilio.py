"""Twilio adapter: SMS + WhatsApp via the Messages API (stdlib only).

WhatsApp notes, stated plainly:
  * Free-form text only works inside the 24-hour customer-service window
    (i.e. after the user messaged you). Business-initiated WhatsApp
    messages need an approved template — use the Meta provider for those.
  * The recipient must have opted in to WhatsApp messages from your number.
"""

import base64
import json
import urllib.error
import urllib.parse
import urllib.request

from ..config import Settings
from .base import BaseProvider, ProviderError, SendResult


class TwilioProvider(BaseProvider):
    name = "twilio"

    def __init__(self, settings: Settings) -> None:
        if not settings.twilio_account_sid or not settings.twilio_auth_token:
            raise ProviderError(
                "Twilio selected but TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN"
                " are not set")
        self._sid = settings.twilio_account_sid
        self._token = settings.twilio_auth_token
        self._sms_from = settings.twilio_sms_from
        self._wa_from = settings.twilio_whatsapp_from
        self._url = ("https://api.twilio.com/2010-04-01/Accounts/"
                     f"{self._sid}/Messages.json")

    def send(self, *, to: str, body: str, channel: str,
             template_name: str | None = None,
             template_language: str | None = None,
             media_url: str | None = None) -> SendResult:
        if channel == "sms":
            sender, dest = self._sms_from, to
            if not sender:
                raise ProviderError("TWILIO_SMS_FROM is not set")
        elif channel == "whatsapp":
            if template_name:
                raise ProviderError(
                    "Twilio adapter sends free-form WhatsApp text only;"
                    " use the Meta provider for template messages")
            sender = f"whatsapp:{self._wa_from}" if self._wa_from else None
            dest = f"whatsapp:{to}"
            if not sender:
                raise ProviderError("TWILIO_WHATSAPP_FROM is not set")
        else:
            raise ProviderError(f"Twilio does not support channel '{channel}'")

        fields = {"To": dest, "From": sender, "Body": body}
        if media_url:
            fields["MediaUrl"] = media_url
        data = urllib.parse.urlencode(fields).encode()
        auth = base64.b64encode(f"{self._sid}:{self._token}".encode()).decode()
        req = urllib.request.Request(
            self._url, data=data,
            headers={"Authorization": f"Basic {auth}"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            raise ProviderError(
                f"Twilio rejected the message ({exc.code}): "
                f"{exc.read().decode(errors='replace')[:300]}")
        except OSError as exc:
            raise ProviderError(f"Twilio request failed: {exc}")
        return SendResult(
            provider_message_id=payload.get("sid", ""),
            status="sent",
            raw=payload,
        )
