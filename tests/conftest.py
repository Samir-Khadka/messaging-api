"""Test client with an isolated temp DB and test credentials.

Settings are read when the app lifespan starts (on TestClient entry),
so env vars are set in the fixture before entering the client.
"""

import os

import pytest
from fastapi.testclient import TestClient

from app.main import app

API_KEY = "test-key-123"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DEV_MODE", "true")
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("MESSAGING_API_KEYS", API_KEY)
    monkeypatch.setenv("OTP_RESEND_COOLDOWN_SECONDS", "0")
    monkeypatch.setenv("OTP_MAX_SENDS_PER_HOUR", "100")
    monkeypatch.setenv("META_VERIFY_TOKEN", "verify-me")
    with TestClient(app) as c:
        c.headers.update({"X-API-Key": API_KEY})
        yield c
