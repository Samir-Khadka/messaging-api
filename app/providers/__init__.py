"""Provider registry: one provider object per channel, chosen by env.

Provider names: console | twilio | meta | rcs
  sms      -> console, twilio
  whatsapp -> console, twilio, meta
  rcs      -> console, rcs
"""

from ..config import Settings
from .base import BaseProvider, ProviderError
from .console import ConsoleProvider
from .meta import MetaWhatsAppProvider
from .rcs import RcsProvider
from .twilio import TwilioProvider

_ALLOWED = {
    "sms": {"console", "twilio"},
    "whatsapp": {"console", "twilio", "meta"},
    "rcs": {"console", "rcs"},
}


def build_providers(settings: Settings) -> dict[str, BaseProvider]:
    providers: dict[str, BaseProvider] = {}
    for channel in ("sms", "whatsapp", "rcs"):
        name = settings.provider_for(channel)
        if name not in _ALLOWED[channel]:
            raise ProviderError(
                f"provider '{name}' does not support channel '{channel}'"
                f" (allowed: {sorted(_ALLOWED[channel])})")
        if name == "console":
            providers[channel] = ConsoleProvider()
        elif name == "twilio":
            providers[channel] = TwilioProvider(settings)
        elif name == "meta":
            providers[channel] = MetaWhatsAppProvider(settings)
        elif name == "rcs":
            providers[channel] = RcsProvider(settings)
    return providers
