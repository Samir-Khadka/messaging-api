"""Provider contract. Every channel adapter implements this, so adding a
new vendor (Vonage, Sinch, a local Nepali gateway like Sparrow SMS) is
one new file + one line in the registry."""

from dataclasses import dataclass


class ProviderError(Exception):
    """Raised when the vendor rejects or cannot deliver a message."""


@dataclass
class SendResult:
    provider_message_id: str
    status: str  # "sent" | "logged" (console provider)
    raw: dict | None = None


class BaseProvider:
    name: str = "base"

    def send(self, *, to: str, body: str, channel: str,
             template_name: str | None = None,
             template_language: str | None = None,
             media_url: str | None = None) -> SendResult:
        raise NotImplementedError
