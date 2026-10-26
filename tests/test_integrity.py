from uuid import UUID

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from app.db.models import MAX_AMOUNT, SYSTEM_ACCOUNT_ID, Account, IdempotencyRecord, Transfer
from app.schemas.transfer import TransferCreate
from app.services.transfer_service import transfer_money
from tests.conftest import payload


def test_stale_identity_map_is_refreshed_after_lock(accounts, sessions):
    with sessions() as stale:
        cached = stale.get(Account, UUID(accounts[0]))
        assert cached.balance == 10000
        with sessions.begin() as other:
            transfer_money(other, TransferCreate(**payload(accounts, 8000)))
        # The old identity-map value must not allow another 8,000 debit.
        from app.core.exceptions import DomainError

        with pytest.raises(DomainError, match="Insufficient funds"):
            transfer_money(stale, TransferCreate(**payload(accounts, 8000)))
        stale.rollback()
    with sessions() as session:
        assert session.get(Account, UUID(accounts[0])).balance == 2000


def test_account_identity_is_immutable(accounts, sessions):
    with pytest.raises(IntegrityError), sessions.begin() as session:
        session.get(Account, SYSTEM_ACCOUNT_ID).is_system = False


def test_unfinished_key_cannot_commit(sessions):
    with pytest.raises(IntegrityError), sessions.begin() as session:
        session.add(IdempotencyRecord(key="unfinished", operation="transfer", fingerprint="a" * 64))


def test_completed_key_cannot_change(client, accounts, sessions):
    client.post("/transfers", json=payload(accounts), headers={"Idempotency-Key": "immutable"})
    with pytest.raises(IntegrityError), sessions.begin() as session:
        record = session.scalar(
            select(IdempotencyRecord).where(IdempotencyRecord.key == "immutable")
        )
        record.fingerprint = "b" * 64


def test_funding_system_account_returns_404(client):
    response = client.post(
        "/dev/funding", json={"destination_account_id": str(SYSTEM_ACCOUNT_ID), "amount": 1}
    )
    assert response.status_code == 404


def test_balance_limits_rollback(client, sessions):
    source = client.post("/accounts", json={}).json()["id"]
    target = client.post("/accounts", json={}).json()["id"]
    response = client.post(
        "/dev/funding", json={"destination_account_id": source, "amount": MAX_AMOUNT}
    )
    assert response.status_code == 201, response.text
    response = client.post("/dev/funding", json={"destination_account_id": target, "amount": 1})
    assert response.status_code == 409
    assert response.json()["code"] == "balance_limit_exceeded"
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(Transfer)) == 1


def test_updates_to_journal_are_rejected(accounts, sessions):
    for table in ("ledger_entries", "transfers"):
        with pytest.raises(IntegrityError), sessions.begin() as session:
            session.execute(text(f"UPDATE {table} SET amount = amount + 1"))
