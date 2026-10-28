def test_send_sms_console_logs_not_sends(client):
    resp = client.post("/v1/messages", json={
        "to": "+9779862853613", "channel": "sms", "body": "Hello from the API"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "logged"  # console provider: recorded, not sent
    assert data["provider"] == "console"
    assert data["to"] == "+9779862853613"

    fetched = client.get(f"/v1/messages/{data['id']}").json()
    assert fetched["id"] == data["id"]


def test_send_whatsapp_and_rcs(client):
    for channel in ("whatsapp", "rcs"):
        resp = client.post("/v1/messages", json={
            "to": "+9779800000001", "channel": channel, "body": "hi"})
        assert resp.status_code == 200
        assert resp.json()["channel"] == channel


def test_whatsapp_with_fallback_to_sms(client):
    resp = client.post("/v1/messages", json={
        "to": "+9779800000002", "channel": "whatsapp", "body": "hi",
        "fallback_channel": "sms"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "logged"


def test_idempotency_key_returns_same_message(client):
    headers = {"Idempotency-Key": "order-42"}
    first = client.post("/v1/messages", json={
        "to": "+9779800000003", "channel": "sms", "body": "once"},
        headers=headers).json()
    second = client.post("/v1/messages", json={
        "to": "+9779800000003", "channel": "sms", "body": "once"},
        headers=headers).json()
    assert first["id"] == second["id"]
    listed = client.get("/v1/messages").json()["messages"]
    assert sum(1 for m in listed if m["id"] == first["id"]) == 1


def test_invalid_phone_rejected(client):
    resp = client.post("/v1/messages", json={
        "to": "not-a-phone", "channel": "sms", "body": "hi"})
    assert resp.status_code == 422


def test_unknown_channel_rejected(client):
    resp = client.post("/v1/messages", json={
        "to": "+9779800000004", "channel": "pigeon", "body": "hi"})
    assert resp.status_code == 422


def test_unknown_message_404(client):
    assert client.get("/v1/messages/does-not-exist").status_code == 404
