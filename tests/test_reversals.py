from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db.models import Transfer
from tests.conftest import payload


def test_reversal_preserves_original_and_returns_funds(client, accounts):
    original = client.post("/transfers", json=payload(accounts, 1500)).json()
    path = f"/transfers/{original['id']}/reversal"
    headers = {"Idempotency-Key": "refund-1"}
    reversal = client.post(path, json={"reason": "Customer request"}, headers=headers)
    assert reversal.status_code == 201, reversal.text
    assert reversal.json()["reversal_of"] == original["id"]
    assert reversal.json()["source_account_id"] == accounts[1]
    assert (
        client.post(path, json={"reason": "Customer request"}, headers=headers).json()
        == reversal.json()
    )
    assert client.get(f"/transfers/{original['id']}").json() == original
    assert client.get(f"/accounts/{accounts[0]}/balance").json()["balance"] == 10000
    assert client.get(f"/accounts/{accounts[1]}/balance").json()["balance"] == 0
    assert client.post(path, json={"reason": "Again"}).json()["code"] == "already_reversed"
    assert client.post(path, json={"reason": "Changed"}, headers=headers).status_code == 409
    response = client.post(f"/transfers/{reversal.json()['id']}/reversal", json={"reason": "Again"})
    assert response.json()["code"] == "reversal_not_allowed"


def test_reversal_cannot_overdraw_and_key_rolls_back(client, accounts):
    original = client.post("/transfers", json=payload(accounts, 1000)).json()
    assert client.post("/transfers", json=payload(accounts[::-1], 1000)).status_code == 201
    path = f"/transfers/{original['id']}/reversal"
    headers = {"Idempotency-Key": "retry-refund"}
    response = client.post(path, json={"reason": "Refund"}, headers=headers)
    assert response.status_code == 409
    assert response.json()["code"] == "insufficient_funds"
    client.post("/dev/funding", json={"destination_account_id": accounts[1], "amount": 1000})
    assert client.post(path, json={"reason": "Refund"}, headers=headers).status_code == 201


def test_funding_cannot_be_reversed(client, accounts, sessions):
    with sessions() as session:
        funding = session.scalar(select(Transfer))
        funding_id = funding.id
    response = client.post(f"/transfers/{funding_id}/reversal", json={"reason": "No"})
    assert response.status_code == 409


@pytest.mark.parametrize("reason", ["", "   ", "x" * 201])
def test_invalid_reversal_reason(client, accounts, reason):
    transfer = client.post("/transfers", json=payload(accounts)).json()
    assert (
        client.post(f"/transfers/{transfer['id']}/reversal", json={"reason": reason}).status_code
        == 422
    )


def test_database_rejects_incorrect_compensation(client, accounts, sessions):
    original = client.post("/transfers", json=payload(accounts, 1000)).json()
    with pytest.raises(IntegrityError), sessions.begin() as session:
        session.add(
            Transfer(
                **payload(accounts[::-1], 999),
                reversal_of=UUID(original["id"]),
                reversal_reason="Incorrect amount",
            )
        )
