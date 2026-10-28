"""Settings, read from the environment. No secrets are hardcoded.

Production checklist (see README):
  * DEV_MODE=false
  * MESSAGING_API_KEYS set to long random keys
  * OTP_PEPPER set to a long random value
  * HTTPS in front of the service (reverse proxy)
"""

import os


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "") or default)
    except ValueError:
        return default


class Settings:
    def __init__(self) -> None:
        self.dev_mode: bool = _env_bool("DEV_MODE", True)
        self.database_path: str = _env("DATABASE_PATH", "./data/messaging.db")

        keys = [k.strip() for k in _env("MESSAGING_API_KEYS").split(",") if k.strip()]
        if not keys and self.dev_mode:
            keys = ["dev-key-change-me"]
        self.api_keys: list[str] = keys

        self.otp_length: int = _env_int("OTP_LENGTH", 6)
        self.otp_ttl_seconds: int = _env_int("OTP_TTL_SECONDS", 600)
        self.otp_max_attempts: int = _env_int("OTP_MAX_ATTEMPTS", 5)
        self.otp_resend_cooldown_seconds: int = _env_int("OTP_RESEND_COOLDOWN_SECONDS", 60)
        self.otp_max_sends_per_hour: int = _env_int("OTP_MAX_SENDS_PER_HOUR", 5)
        self.otp_pepper: str = _env("OTP_PEPPER") or "dev-pepper-change-me"

        self.sms_provider: str = _env("SMS_PROVIDER", "console").lower()
        self.whatsapp_provider: str = _env("WHATSAPP_PROVIDER", "console").lower()
        self.rcs_provider: str = _env("RCS_PROVIDER", "console").lower()

        self.twilio_account_sid: str = _env("TWILIO_ACCOUNT_SID")
        self.twilio_auth_token: str = _env("TWILIO_AUTH_TOKEN")
        self.twilio_sms_from: str = _env("TWILIO_SMS_FROM")
        self.twilio_whatsapp_from: str = _env("TWILIO_WHATSAPP_FROM")

        self.meta_access_token: str = _env("META_ACCESS_TOKEN")
        self.meta_phone_number_id: str = _env("META_PHONE_NUMBER_ID")
        self.meta_api_version: str = _env("META_API_VERSION", "v21.0")
        self.meta_verify_token: str = _env("META_VERIFY_TOKEN")

        self.rcs_provider_url: str = _env("RCS_PROVIDER_URL")
        self.rcs_provider_token: str = _env("RCS_PROVIDER_TOKEN")

    def provider_for(self, channel: str) -> str:
        return {
            "sms": self.sms_provider,
            "whatsapp": self.whatsapp_provider,
            "rcs": self.rcs_provider,
        }[channel]
