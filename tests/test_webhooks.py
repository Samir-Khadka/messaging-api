def test_twilio_receipt_updates_status(client):
    sent = client.post("/v1/messages", json={
        "to": "+9779855555555", "channel": "sms", "body": "hi"}).json()
    resp = client.post("/v1/webhooks/twilio", data={
        "MessageSid": sent["provider_message_id"],
        "MessageStatus": "delivered",
        "From": "+9779855555555",
    })
    assert resp.status_code == 200
    fetched = client.get(f"/v1/messages/{sent['id']}").json()
    assert fetched["status"] == "delivered"


def test_meta_verify_handshake(client):
    ok = client.get("/v1/webhooks/meta", params={
        "hub_mode": "subscribe", "hub_verify_token": "verify-me",
        "hub_challenge": "challenge-123"})
    assert ok.text == "challenge-123"
    bad = client.get("/v1/webhooks/meta", params={
        "hub_mode": "subscribe", "hub_verify_token": "wrong",
        "hub_challenge": "challenge-123"})
    assert bad.status_code == 403


def test_meta_status_webhook(client):
    sent = client.post("/v1/messages", json={
        "to": "+9779866666666", "channel": "whatsapp", "body": "hi"}).json()
    payload = {"entry": [{"changes": [{"value": {"statuses": [{
        "id": sent["provider_message_id"], "status": "read"}]}}]}]}
    resp = client.post("/v1/webhooks/meta", json=payload)
    assert resp.status_code == 200
    fetched = client.get(f"/v1/messages/{sent['id']}").json()
    assert fetched["status"] == "read"
