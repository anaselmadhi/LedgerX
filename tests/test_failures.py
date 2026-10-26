from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from app.db.models import Account, IdempotencyRecord, LedgerEntry, Transfer
from app.services import transfer_service
from tests.conftest import payload


def test_http_crash_after_flush_is_atomic_and_safe_to_retry(
    client, accounts, sessions, monkeypatch
):
    original = transfer_service.post_entries

    def crash(session, transfer):
        original(session, transfer)
        raise RuntimeError("Injected crash")

    monkeypatch.setattr(transfer_service, "post_entries", crash)
    headers = {"Idempotency-Key": "http-crash", "X-Correlation-ID": "rollback-case"}
    failed = client.post("/transfers", json=payload(accounts), headers=headers)
    assert failed.status_code == 500
    assert failed.json()["code"] == "internal_error"
    with sessions() as session:
        assert session.get(Account, UUID(accounts[0])).balance == 10000
        assert session.get(Account, UUID(accounts[1])).balance == 0
        assert session.scalar(select(func.count()).select_from(Transfer)) == 1
        assert session.scalar(select(func.count()).select_from(LedgerEntry)) == 2
        assert (
            session.scalar(select(IdempotencyRecord).where(IdempotencyRecord.key == "http-crash"))
            is None
        )
    monkeypatch.setattr(transfer_service, "post_entries", original)
    assert client.post("/transfers", json=payload(accounts), headers=headers).status_code == 201
    assert client.get("/operations/reconciliation").json()["consistent"] is True


def test_database_failure_is_sanitized_and_retryable(client, accounts, monkeypatch, caplog):
    def unavailable(*args, **kwargs):
        raise OperationalError("secret SQL", {"password": "must-not-leak"}, OSError("private-host"))

    monkeypatch.setattr(transfer_service, "post_entries", unavailable)
    response = client.post(
        "/transfers", json=payload(accounts), headers={"Idempotency-Key": "database-outage"}
    )
    assert response.status_code == 503
    assert response.headers["retry-after"] == "1"
    assert response.json()["code"] == "database_temporarily_unavailable"
    assert "must-not-leak" not in response.text + caplog.text
    assert "private-host" not in response.text + caplog.text
    assert client.get("/operations/reconciliation").json()["consistent"] is True
