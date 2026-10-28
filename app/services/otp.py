"""OTP lifecycle: request -> verify.

Security properties, all deliberate:
  * Codes are 6 digits from secrets (not random).
  * Only an HMAC-SHA256 hash is stored. The plaintext code is stored
    ONLY when DEV_MODE=true (dev_code column) so local testing works;
    in production the code exists nowhere after sending.
  * One active code per phone: a new request supersedes the old one.
  * Cooldown between sends + hourly cap per phone (abuse resistance).
  * Fixed attempt budget; exceeding it burns the code.
  * Verify responses never say "wrong digit vs expired" differently
    than needed: reasons are returned for the caller's UX, but the code
    itself is never echoed.
"""

import hashlib
import hmac
import secrets
import time

from ..config import Settings
from ..db import Database
from ..providers.base import BaseProvider
from ..security import normalize_phone
from . import messaging


class OtpRateLimited(Exception):
    pass


def _hash_code(settings: Settings, code: str) -> str:
    return hmac.new(settings.otp_pepper.encode(), code.encode(),
                    hashlib.sha256).hexdigest()


def request_otp(db: Database, providers: dict[str, BaseProvider],
                settings: Settings, *, phone: str,
                channel: str = "sms") -> dict:
    phone = normalize_phone(phone)
    now = time.time()
    last = db.last_otp_sent_at(phone)
    if last and now - last < settings.otp_resend_cooldown_seconds:
        raise OtpRateLimited(
            f"wait {settings.otp_resend_cooldown_seconds}s between OTP sends")
    if db.count_recent_otp_sends(phone, now - 3600) >= settings.otp_max_sends_per_hour:
        raise OtpRateLimited("hourly OTP limit reached for this number")

    code = "".join(secrets.choice("0123456789")
                   for _ in range(settings.otp_length))
    db.invalidate_active_otps(phone)
    row = db.insert_otp(
        phone=phone, code_hash=_hash_code(settings, code),
        dev_code=code if settings.dev_mode else None,
        channel=channel, expires_at=now + settings.otp_ttl_seconds)

    minutes = max(1, settings.otp_ttl_seconds // 60)
    messaging.send_message(
        db, providers, to=phone, channel=channel,
        body=f"Your verification code is {code}. It expires in {minutes}"
             f" minute(s). Do not share it with anyone.")
    return {
        "phone": phone,
        "channel": channel,
        "expires_in_seconds": settings.otp_ttl_seconds,
        "otp_id": row["id"],
    }


def verify_otp(db: Database, settings: Settings, *, phone: str,
               code: str) -> tuple[bool, str]:
    phone = normalize_phone(phone)
    row = db.get_active_otp(phone)
    if not row:
        latest = db.get_latest_otp(phone)
        if latest and latest["status"] == "locked":
            return False, "too_many_attempts"
        return False, "no_active_code"
    if time.time() > row["expires_at"]:
        db.update_otp(row["id"], status="expired")
        return False, "expired"
    if row["attempts"] >= settings.otp_max_attempts:
        db.update_otp(row["id"], status="locked")
        return False, "too_many_attempts"
    if hmac.compare_digest(row["code_hash"], _hash_code(settings, code.strip())):
        db.update_otp(row["id"], status="used")
        return True, "verified"
    attempts = row["attempts"] + 1
    status = "locked" if attempts >= settings.otp_max_attempts else "active"
    db.update_otp(row["id"], attempts=attempts, status=status)
    return False, "incorrect"
