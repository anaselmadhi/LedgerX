from tests.conftest import payload


def test_retry_and_conflict(client, accounts):
    headers = {"Idempotency-Key": "payment-1"}
    first = client.post("/transfers", json=payload(accounts), headers=headers)
    second = client.post("/transfers", json=payload(accounts), headers=headers)
    assert first.status_code == second.status_code == 201
    assert first.json() == second.json()
    conflict = client.post("/transfers", json=payload(accounts, 2000), headers=headers)
    assert conflict.status_code == 409
    assert client.get(f"/accounts/{accounts[0]}/balance").json()["balance"] == 9000


def test_failed_request_does_not_reserve_key(client, accounts):
    headers = {"Idempotency-Key": "retry-after-funding"}
    body = payload(accounts, 11000)
    assert client.post("/transfers", json=body, headers=headers).status_code == 409
    assert (
        client.post(
            "/dev/funding", json={"destination_account_id": accounts[0], "amount": 1000}
        ).status_code
        == 201
    )
    result = client.post("/transfers", json=body, headers=headers)
    assert result.status_code == 201
    assert client.post("/transfers", json=body, headers=headers).json() == result.json()


def test_key_validation(client, accounts):
    response = client.post("/transfers", json=payload(accounts), headers={"Idempotency-Key": ""})
    assert response.status_code == 422


def test_failed_request_allows_different_payload(client, accounts):
    headers = {"Idempotency-Key": "not-reserved-on-failure"}
    assert (
        client.post("/transfers", json=payload(accounts, 20000), headers=headers).status_code == 409
    )
    assert (
        client.post("/transfers", json=payload(accounts, 500), headers=headers).status_code == 201
    )


def test_default_currency_is_canonical(client, accounts):
    headers = {"Idempotency-Key": "normalized"}
    body = payload(accounts)
    first = client.post("/transfers", json=body, headers=headers)
    del body["currency"]
    second = client.post("/transfers", json=body, headers=headers)
    assert first.status_code == second.status_code == 201
    assert first.json() == second.json()


def test_funding_is_idempotent_and_scoped(client, accounts):
    headers = {"Idempotency-Key": "same-key-different-operation"}
    body = {"destination_account_id": accounts[0], "amount": 500}
    first = client.post("/dev/funding", json=body, headers=headers)
    replay = client.post("/dev/funding", json=body, headers=headers)
    assert first.status_code == replay.status_code == 201
    assert first.json() == replay.json()
    transfer = client.post("/transfers", json=payload(accounts, 500), headers=headers)
    assert transfer.status_code == 201
    assert transfer.json()["id"] != first.json()["id"]
    assert client.get(f"/accounts/{accounts[0]}/balance").json()["balance"] == 10000
