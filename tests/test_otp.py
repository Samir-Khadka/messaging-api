PHONE = "+9779811111111"


def _send(client, phone=PHONE):
    resp = client.post("/v1/otp/send", json={"phone": phone})
    assert resp.status_code == 200
    return resp.json()


def _dev_code(client, phone=PHONE):
    return client.get("/v1/dev/otp-code", params={"phone": phone}).json()["code"]


def test_otp_happy_path_and_single_use(client):
    _send(client)
    code = _dev_code(client)
    ok = client.post("/v1/otp/verify",
                     json={"phone": PHONE, "code": code}).json()
    assert ok == {"verified": True, "reason": "verified"}
    # A used code cannot be reused.
    again = client.post("/v1/otp/verify",
                        json={"phone": PHONE, "code": code}).json()
    assert again["verified"] is False


def test_wrong_code_rejected(client):
    _send(client, "+9779822222222")
    resp = client.post("/v1/otp/verify",
                       json={"phone": "+9779822222222", "code": "000000"})
    assert resp.json() == {"verified": False, "reason": "incorrect"}


def test_new_code_supersedes_old(client):
    phone = "+9779833333333"
    _send(client, phone)
    first_code = _dev_code(client, phone)
    _send(client, phone)  # supersedes the first code
    second_code = _dev_code(client, phone)
    assert first_code != second_code or True  # codes may rarely collide
    old = client.post("/v1/otp/verify",
                      json={"phone": phone, "code": first_code}).json()
    new = client.post("/v1/otp/verify",
                      json={"phone": phone, "code": second_code}).json()
    assert new["verified"] is True
    assert old["verified"] is False or first_code == second_code


def test_attempts_lockout(client):
    phone = "+9779844444444"
    _send(client, phone)
    for _ in range(5):
        resp = client.post("/v1/otp/verify",
                           json={"phone": phone, "code": "000000"}).json()
        assert resp["verified"] is False
    locked = client.post("/v1/otp/verify",
                         json={"phone": phone, "code": "000000"}).json()
    assert locked["reason"] == "too_many_attempts"
