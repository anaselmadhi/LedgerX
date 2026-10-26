from uuid import uuid4

from app.core.config import settings


def test_account_creation_and_balance(client):
    response = client.post("/accounts", json={"currency": "EUR"})
    assert response.status_code == 201
    account = response.json()
    assert account["balance"] == 0
    assert client.get(f"/accounts/{account['id']}").json() == account
    assert client.get(f"/accounts/{account['id']}/balance").json()["balance"] == 0
    assert client.get(f"/accounts/{uuid4()}").status_code == 404
    assert client.post("/accounts", json={"currency": "USD"}).status_code == 422


def test_history_pagination(client, accounts):
    response = client.get(f"/accounts/{accounts[0]}/transactions?limit=1&offset=0")
    assert response.status_code == 200
    assert len(response.json()["items"]) == 1
    entry = response.json()["items"][0]
    assert entry["account_id"] == accounts[0]
    assert entry["amount"] == 10000
    assert client.get(f"/accounts/{accounts[1]}/transactions").json()["items"] == []
    assert client.get(f"/accounts/{accounts[0]}/transactions?offset=1").json()["items"] == []
    assert client.get(f"/accounts/{accounts[0]}/transactions?limit=101").status_code == 422


def test_funding_disabled(client, accounts, monkeypatch):
    monkeypatch.setattr(settings, "enable_dev_funding", False)
    response = client.post(
        "/dev/funding", json={"destination_account_id": accounts[0], "amount": 1}
    )
    assert response.status_code == 404


def test_cursor_pages_with_tied_timestamps_and_new_entries(client, accounts, sessions):
    from app.schemas.transfer import TransferCreate
    from app.services.transfer_service import transfer_money
    from tests.conftest import payload

    # PostgreSQL now() is identical for all writes in this transaction.
    with sessions.begin() as session:
        for _ in range(5):
            transfer_money(session, TransferCreate(**payload(accounts, 10)))
    path = f"/accounts/{accounts[0]}/transactions"
    expected = client.get(path).json()["items"]
    page = client.get(path, params={"limit": 2}).json()
    seen = page["items"]
    client.post("/transfers", json=payload(accounts, 10))
    while page["next_cursor"]:
        page = client.get(path, params={"limit": 2, "cursor": page["next_cursor"]}).json()
        seen += page["items"]
    assert [row["id"] for row in seen] == [row["id"] for row in expected]
    assert len({row["id"] for row in seen}) == 6
    cursor = client.get(path, params={"limit": 1}).json()["next_cursor"]
    assert client.get(path, params={"cursor": cursor, "offset": 1}).status_code == 422
    assert (
        client.get(f"/accounts/{accounts[1]}/transactions", params={"cursor": cursor}).status_code
        == 422
    )
