"""Dev provider: records the message, delivers nothing.

This is the default for every channel, so the API works end-to-end with
zero credentials — the same idea as Kishan-Bazzar's demo-mode OTP, but
labelled honestly: status is "logged", never "sent". Swap a channel to a
real provider in .env when you have credentials.
"""

import logging
import uuid

from .base import BaseProvider, SendResult

log = logging.getLogger("messaging.console")


class ConsoleProvider(BaseProvider):
    name = "console"

    def send(self, *, to: str, body: str, channel: str,
             template_name: str | None = None,
             template_language: str | None = None,
             media_url: str | None = None) -> SendResult:
        # Bodies are NOT printed here: OTP codes travel inside bodies.
        log.info("console provider: %s message to %s recorded (not sent)",
                 channel, to)
        return SendResult(
            provider_message_id=f"console-{uuid.uuid4().hex[:12]}",
            status="logged",
            raw={"channel": channel, "template": template_name},
        )
