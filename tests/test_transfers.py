from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from app.db.models import SYSTEM_USER_ID, Account, IdempotencyRecord, LedgerEntry, Transfer
from app.schemas.transfer import TransferCreate
from app.services import transfer_service
from tests.conftest import payload


def test_success_balanced_and_retrievable(client, accounts, sessions):
    response = client.post("/transfers", json=payload(accounts, 1500))
    assert response.status_code == 201, response.text
    transaction_id = response.json()["id"]
    assert client.get(f"/transfers/{transaction_id}").json() == response.json()
    assert client.get(f"/accounts/{accounts[0]}/balance").json()["balance"] == 8500
    assert client.get(f"/accounts/{accounts[1]}/balance").json()["balance"] == 1500
    with sessions() as session:
        entries = session.scalars(
            select(LedgerEntry).where(LedgerEntry.transaction_id == UUID(transaction_id))
        ).all()
        assert len(entries) == 2
        assert sorted(entry.amount for entry in entries) == [-1500, 1500]
        assert sum(entry.amount for entry in entries) == 0
        for account in session.scalars(select(Account)):
            total = session.scalar(
                select(func.coalesce(func.sum(LedgerEntry.amount), 0)).where(
                    LedgerEntry.account_id == account.id
                )
            )
            assert account.balance == total


def test_insufficient_funds(client, accounts):
    assert client.post("/transfers", json=payload(accounts, 10001)).status_code == 409
    assert client.get(f"/accounts/{accounts[0]}/balance").json()["balance"] == 10000


@pytest.mark.parametrize("amount", [0, -1, 0.5, True, "100", 10**20])
def test_invalid_transfer_amount(client, accounts, amount):
    assert client.post("/transfers", json=payload(accounts, amount)).status_code == 422


def test_same_account_currency_missing_and_system(client, accounts):
    body = payload(accounts)
    body["destination_account_id"] = body["source_account_id"]
    assert client.post("/transfers", json=body).status_code == 422
    body = payload(accounts) | {"currency": "USD"}
    assert client.post("/transfers", json=body).status_code == 422
    body = payload(accounts) | {"destination_account_id": str(uuid4())}
    assert client.post("/transfers", json=body).status_code == 404
    body["destination_account_id"] = "00000000-0000-0000-0000-000000000001"
    assert client.post("/transfers", json=body).status_code == 404
    assert client.get(f"/transfers/{uuid4()}").status_code == 404


def test_rollback_after_partial_write(accounts, sessions, monkeypatch):
    original = transfer_service.post_entries

    def fail_after_entries(session, transfer):
        original(session, transfer)
        raise RuntimeError("Injected crash after entries and balances were flushed")

    monkeypatch.setattr(transfer_service, "post_entries", fail_after_entries)
    with pytest.raises(RuntimeError), sessions.begin() as session:
        transfer_service.transfer_money(session, TransferCreate(**payload(accounts)), "rollback")
    with sessions() as session:
        assert session.get(Account, UUID(accounts[0])).balance == 10000
        assert session.get(Account, UUID(accounts[1])).balance == 0
        assert session.scalar(select(func.count()).select_from(Transfer)) == 1  # funding only
        assert session.scalar(select(func.count()).select_from(LedgerEntry)) == 2
        assert session.get(IdempotencyRecord, (SYSTEM_USER_ID, "transfer", "rollback")) is None


def test_database_rejects_unbalanced_transfer(accounts, sessions):
    with pytest.raises(IntegrityError), sessions.begin() as session:
        session.add(Transfer(**payload(accounts)))


def test_database_rejects_independent_balance_update(accounts, sessions):
    with pytest.raises(IntegrityError), sessions.begin() as session:
        account = session.get(Account, UUID(accounts[0]))
        account.balance += 1


def test_journal_immutable(accounts, sessions):
    for table in ("ledger_entries", "transfers"):
        with pytest.raises(IntegrityError), sessions.begin() as session:
            session.execute(text(f"DELETE FROM {table}"))
