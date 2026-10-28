from fastapi.testclient import TestClient

from app.main import app


def test_health_needs_no_key(client):
    assert client.get("/health").json() == {"ok": True}


def test_missing_key_rejected(client):
    with TestClient(app) as bare:
        assert bare.get("/v1/status").status_code == 401


def test_wrong_key_rejected(client):
    with TestClient(app) as bare:
        resp = bare.get("/v1/status", headers={"X-API-Key": "nope"})
        assert resp.status_code == 401


def test_status_shows_console_providers_in_dev(client):
    resp = client.get("/v1/status")
    assert resp.status_code == 200
    assert resp.json()["providers"] == {
        "sms": "console", "whatsapp": "console", "rcs": "console",
    }
    assert resp.json()["dev_mode"] is True
