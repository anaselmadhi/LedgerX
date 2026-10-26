from uuid import uuid4

from app.db.models import Account
from tests.conftest import payload


def test_readiness_and_liveness(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["schema"] == "0004"
    assert client.get("/health/live").json() == {"status": "ok"}


def test_reconciliation_uses_database_state(client, accounts):
    client.post("/transfers", json=payload(accounts))
    result = client.get("/operations/reconciliation").json()
    assert result.pop("checked_at")
    assert result == {
        "consistent": True,
        "account_count": 3,
        "transfer_count": 2,
        "entry_count": 4,
        "mismatched_accounts": 0,
        "projection_mismatched_accounts": 0,
        "invalid_transfers": 0,
        "total_balance": 0,
        "ledger_total": 0,
        "discrepancies": [],
        "projection_discrepancies": [],
        "discrepancy_sample_limit": 100,
    }


def test_independent_audit_detects_corruption_without_repair(client, accounts, sessions):
    from uuid import UUID

    from sqlalchemy import text

    # Intentional fault injection only on the conftest-guarded disposable _test DB.
    # Re-enable the trigger in the same transaction; no production path bypasses it.
    with sessions.begin() as session:
        session.execute(text("ALTER TABLE accounts DISABLE TRIGGER account_matches_ledger"))
        session.execute(
            text("UPDATE accounts SET balance = balance + 7 WHERE id = :id"),
            {"id": UUID(accounts[0])},
        )
        session.execute(text("ALTER TABLE accounts ENABLE TRIGGER account_matches_ledger"))
    try:
        response = client.get("/operations/reconciliation")
        assert response.status_code == 200
        report = response.json()
        assert report["consistent"] is False
        assert report["mismatched_accounts"] == 1
        assert report["discrepancies"] == [
            {
                "account_id": accounts[0],
                "stored_balance": 10007,
                "journal_balance": 10000,
                "difference": 7,
            }
        ]
        with sessions() as session:
            assert session.get(Account, UUID(accounts[0])).balance == 10007
    finally:
        with sessions.begin() as session:
            session.execute(
                text("UPDATE accounts SET balance = balance - 7 WHERE id = :id"),
                {"id": UUID(accounts[0])},
            )


def test_request_id_and_bounded_metric_labels(client, accounts):
    response = client.get(f"/accounts/{accounts[0]}", headers={"X-Request-ID": "demo-123"})
    assert response.headers["x-request-id"] == "demo-123"
    unknown = str(uuid4())
    assert client.get(f"/accounts/{unknown}").status_code == 404
    metrics = client.get("/metrics").text
    assert "ledgerx_http_request_duration_seconds_bucket" in metrics
    assert 'route="/accounts/{account_id}"' in metrics
    assert unknown not in metrics
    invalid = client.get("/health/live", headers={"X-Request-ID": "unsafe id"})
    assert invalid.headers["x-request-id"] != "unsafe id"


def test_lock_timeout_is_retryable_and_does_not_spend(client, accounts, sessions, monkeypatch):
    from uuid import UUID

    from sqlalchemy import select, text

    from app.db.session import get_session
    from app.main import app

    def impatient_session():
        with sessions() as session:
            # Configure connection outside Session.begin(), preserving route ownership.
            from sqlalchemy import event

            def set_timeout(session, transaction, connection):
                connection.execute(text("SET LOCAL lock_timeout = '50ms'"))

            event.listen(session, "after_begin", set_timeout)
            yield session

    previous = app.dependency_overrides[get_session]
    app.dependency_overrides[get_session] = impatient_session
    try:
        with sessions.begin() as holder:
            holder.scalar(select(Account).where(Account.id == UUID(accounts[0])).with_for_update())
            response = client.post(
                "/transfers", json=payload(accounts), headers={"Idempotency-Key": "timed-out"}
            )
            assert response.status_code == 503, response.text
            assert response.headers["retry-after"] == "1"
    finally:
        app.dependency_overrides[get_session] = previous
    retry = client.post(
        "/transfers", json=payload(accounts), headers={"Idempotency-Key": "timed-out"}
    )
    assert retry.status_code == 201
    assert client.get(f"/accounts/{accounts[0]}/balance").json()["balance"] == 9000
