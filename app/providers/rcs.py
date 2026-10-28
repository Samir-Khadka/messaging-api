"""Generic RCS adapter (RCS only).

Honest scope: real RCS delivery goes through Google RCS Business
Messaging (RBM) and needs a registered, verified RBM agent plus a partner
endpoint — there is no public "just send RCS" API. This adapter POSTs a
simple JSON envelope to whatever RBM-compatible endpoint you configure
(RCS_PROVIDER_URL + RCS_PROVIDER_TOKEN) and surfaces that endpoint's
message id. If you have no RBM agent, leave RCS_PROVIDER=console: the
message is recorded, not sent, and the API says so.

To wire a real RBM partner, implement their exact request shape in this
file — the rest of the service (routing, storage, OTP) does not change.
"""

import json
import urllib.error
import urllib.request

from ..config import Settings
from .base import BaseProvider, ProviderError, SendResult


class RcsProvider(BaseProvider):
    name = "rcs"

    def __init__(self, settings: Settings) -> None:
        if not settings.rcs_provider_url:
            raise ProviderError(
                "RCS selected but RCS_PROVIDER_URL is not set — real RCS"
                " needs a registered RBM agent endpoint (see README)")
        self._url = settings.rcs_provider_url
        self._token = settings.rcs_provider_token

    def send(self, *, to: str, body: str, channel: str,
             template_name: str | None = None,
             template_language: str | None = None,
             media_url: str | None = None) -> SendResult:
        if channel != "rcs":
            raise ProviderError(f"RCS provider supports rcs only, not '{channel}'")
        payload = {"to": to, "body": body}
        if media_url:
            payload["media_url"] = media_url
        headers = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        req = urllib.request.Request(
            self._url, data=json.dumps(payload).encode(),
            headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as exc:
            raise ProviderError(
                f"RCS endpoint rejected the message ({exc.code}): "
                f"{exc.read().decode(errors='replace')[:300]}")
        except OSError as exc:
            raise ProviderError(f"RCS endpoint request failed: {exc}")
        return SendResult(
            provider_message_id=str(
                result.get("message_id") or result.get("id") or ""),
            status="sent",
            raw=result,
        )
