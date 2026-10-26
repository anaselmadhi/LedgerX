"""Real TCP requests against the isolated benchmark API, with no DB fixture."""

import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import httpx
import pytest

from scripts.benchmark import authenticate_benchmark, checked, local_url

pytestmark = pytest.mark.e2e


@pytest.fixture()
def live_client():
    url = os.getenv("E2E_BASE_URL")
    if not url:
        pytest.skip("Set E2E_BASE_URL to a running local API with development funding enabled")
    with httpx.Client(base_url=local_url(url), timeout=20, trust_env=False) as client:
        authenticate_benchmark(client)
        yield client


def test_complete_payment_lifecycle_over_http(live_client):
    client = live_client
    assert checked(client, "GET", "/health", 200)["status"] == "ok"
    source = checked(client, "POST", "/accounts", json={})["id"]
    target = checked(client, "POST", "/accounts", json={})["id"]
    checked(
        client,
        "POST",
        "/dev/funding",
        json={"destination_account_id": source, "amount": 10000},
        headers={"Idempotency-Key": str(uuid4())},
    )
    body = {"source_account_id": source, "destination_account_id": target, "amount": 1500}
    headers = {"Idempotency-Key": str(uuid4()), "X-Request-ID": "e2e-payment"}
    response = client.post("/transfers", json=body, headers=headers)
    assert response.status_code == 201
    assert response.headers["x-request-id"] == "e2e-payment"
    original = response.json()
    assert client.post("/transfers", json=body, headers=headers).json() == original
    assert client.post("/transfers", json=body | {"amount": 1}, headers=headers).status_code == 409
    assert checked(client, "GET", f"/accounts/{source}/balance", 200)["balance"] == 8500
    assert checked(client, "GET", f"/accounts/{target}/balance", 200)["balance"] == 1500
    history = checked(client, "GET", f"/accounts/{source}/transactions?limit=1", 200)
    assert history["items"][0]["amount"] == -1500
    assert history["next_cursor"]
    second = checked(
        client, "GET", f"/accounts/{source}/transactions?cursor={history['next_cursor']}", 200
    )
    assert second["items"][0]["amount"] == 10000
    reversed_transfer = checked(
        client,
        "POST",
        f"/transfers/{original['id']}/reversal",
        json={"reason": "E2E refund"},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert reversed_transfer["reversal_of"] == original["id"]
    assert checked(client, "GET", f"/transfers/{original['id']}", 200) == original
    assert checked(client, "GET", f"/accounts/{source}/balance", 200)["balance"] == 10000
    assert checked(client, "GET", "/operations/reconciliation", 200)["consistent"]


def test_concurrent_http_retries_execute_once(live_client):
    client = live_client
    source = checked(client, "POST", "/accounts", json={})["id"]
    target = checked(client, "POST", "/accounts", json={})["id"]
    checked(client, "POST", "/dev/funding", json={"destination_account_id": source, "amount": 100})
    body = {"source_account_id": source, "destination_account_id": target, "amount": 80}
    headers = {"Idempotency-Key": str(uuid4())}
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(
            pool.map(lambda _: client.post("/transfers", json=body, headers=headers), range(8))
        )
    assert {r.status_code for r in results} == {201}
    assert len({r.json()["id"] for r in results}) == 1
    assert checked(client, "GET", f"/accounts/{source}/balance", 200)["balance"] == 20
    assert checked(client, "GET", "/operations/reconciliation", 200)["consistent"]
