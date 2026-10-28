"""Auth, phone validation, and rate limiting.

Auth is a simple API key in the X-API-Key header. That is enough for a
service-to-service API behind HTTPS; add OAuth/JWT later if you expose it
to browsers or third parties.
"""

import re
import time
from collections import defaultdict

from fastapi import Header, HTTPException

_E164 = re.compile(r"^\+[1-9]\d{6,14}$")


def normalize_phone(raw: str) -> str:
    """Accept E.164 (+97798XXXXXXXX) or a plain digit string, which we
    treat as already country-coded and prefix with '+'. Anything else is
    rejected — guessing a country code silently would misdeliver OTPs."""
    phone = re.sub(r"[\s\-()]", "", raw.strip())
    if not phone.startswith("+"):
        phone = "+" + phone
    if not _E164.match(phone):
        raise ValueError(
            "phone must be E.164, e.g. +9779862853613 (7-15 digits after +)")
    return phone


def require_api_key(x_api_key: str | None = Header(default=None)):
    """FastAPI dependency. The app wires the real key list at startup
    (see main.py); this helper reads it from a module-level slot so the
    dependency stays importable in tests."""
    keys = _KEYS
    if not keys:
        raise HTTPException(status_code=500, detail="server has no API keys configured")
    if x_api_key not in keys:
        raise HTTPException(status_code=401, detail="invalid or missing X-API-Key")
    return x_api_key


_KEYS: list[str] = []


def set_api_keys(keys: list[str]) -> None:
    global _KEYS
    _KEYS = list(keys)


class RateLimiter:
    """In-memory sliding-window limiter. Keyed by any string (API key,
    phone number). Good for one process; use Redis if you scale out."""

    def __init__(self) -> None:
        self._hits: dict[str, list[float]] = defaultdict(list)

    def allow(self, key: str, *, limit: int, window_seconds: float) -> bool:
        now = time.time()
        hits = [t for t in self._hits[key] if t > now - window_seconds]
        if len(hits) >= limit:
            self._hits[key] = hits
            return False
        hits.append(now)
        self._hits[key] = hits
        return True
