"""Adversarial SQL, atomicity and migration checks for the private journal projection."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from sqlalchemy import insert, text
from sqlalchemy.exc import IntegrityError

from alembic import command
from app.db.models import Account, LedgerEntry, Transfer
from app.schemas.transfer import TransferCreate
from app.services.reconciliation_service import reconcile
from app.services.transfer_service import transfer_money
from tests.conftest import payload
from tests.test_migrations import migration_config


def assert_projection(sessions):
    with sessions() as session:
        rows = session.execute(
            text("""
                SELECT a.balance, a.ledger_balance, coalesce(sum(e.amount), 0) AS journal
                FROM accounts a LEFT JOIN ledger_entries e ON e.account_id = a.id
                GROUP BY a.id
            """)
        ).all()
        assert rows
        assert all(row.balance == row.ledger_balance == row.journal for row in rows)
        assert reconcile(session).consistent


@pytest.mark.parametrize("also_forge_balance", [False, True])
def test_direct_projection_change_is_rejected(accounts, sessions, also_forge_balance):
    assignment = "ledger_balance = ledger_balance + 7"
    if also_forge_balance:
        assignment += ", balance = balance + 7"
    with pytest.raises(IntegrityError, match="maintained by ledger inserts"), sessions.begin() as s:
        s.execute(text(f"UPDATE accounts SET {assignment} WHERE id = :id"), {"id": accounts[0]})
    assert_projection(sessions)


def test_new_account_cannot_forge_initial_projection(accounts, sessions):
    with pytest.raises(IntegrityError, match="starts at zero"), sessions.begin() as session:
        owner = session.get(Account, UUID(accounts[0])).owner_id
        session.add(Account(owner_id=owner, balance=7, ledger_balance=7))
    assert_projection(sessions)


def test_bulk_journal_statement_projects_all_entries(accounts, sessions):
    with sessions.begin() as session:
        entries = []
        for amount in (7, 13, 29):
            transfer = Transfer(**payload(accounts, amount))
            session.add(transfer)
            session.flush()
            entries += [
                {
                    "id": uuid4(),
                    "transaction_id": transfer.id,
                    "account_id": UUID(account),
                    "amount": signed_amount,
                    "currency": "EUR",
                }
                for account, signed_amount in ((accounts[0], -amount), (accounts[1], amount))
            ]
        session.execute(
            text("""
                UPDATE accounts SET balance = balance + CASE WHEN id = :source THEN -49 ELSE 49 END
                WHERE id IN (:source, :target)
            """),
            {"source": accounts[0], "target": accounts[1]},
        )
        # One INSERT statement, six journal rows, two grouped account deltas.
        session.execute(insert(LedgerEntry).values(entries))
    assert_projection(sessions)


def test_conflict_ignored_entries_do_not_project_twice(accounts, sessions):
    with sessions.begin() as session:
        session.execute(
            text("INSERT INTO ledger_entries SELECT * FROM ledger_entries ON CONFLICT DO NOTHING")
        )
    assert_projection(sessions)


def test_projection_and_journal_roll_back_to_savepoint(accounts, sessions):
    with sessions.begin() as session:
        with pytest.raises(RuntimeError, match="injected"), session.begin_nested():
            transfer_money(session, TransferCreate(**payload(accounts, 300)), "rolled-back")
            raise RuntimeError("injected after projection")
        transfer_money(session, TransferCreate(**payload(accounts, 17)), "committed")
    with sessions() as session:
        assert session.get(Account, UUID(accounts[0])).balance == 9983
        assert session.get(Account, UUID(accounts[1])).balance == 17
    assert_projection(sessions)


def test_concurrent_projection_increments_are_not_lost(accounts, sessions):
    barrier = Barrier(4)

    def worker(index):
        with sessions.begin() as session:
            barrier.wait(timeout=10)
            for step in range(5):
                transfer_money(
                    session, TransferCreate(**payload(accounts, 7)), f"projection-{index}-{step}"
                )

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(worker, range(4)))
    with sessions() as session:
        assert session.get(Account, UUID(accounts[1])).balance == 140
    assert_projection(sessions)


def test_independent_reconciliation_detects_projection_corruption(accounts, sessions):
    # Fault injection is restricted by conftest to a disposable _test database.
    # No API or operational script disables these triggers.
    with sessions.begin() as session:
        session.execute(text("ALTER TABLE accounts DISABLE TRIGGER immutable_ledger_projection"))
        session.execute(text("ALTER TABLE accounts DISABLE TRIGGER account_matches_ledger"))
        session.execute(
            text("UPDATE accounts SET ledger_balance = ledger_balance + 7 WHERE id = :id"),
            {"id": accounts[0]},
        )
        session.execute(text("ALTER TABLE accounts ENABLE TRIGGER immutable_ledger_projection"))
        session.execute(text("ALTER TABLE accounts ENABLE TRIGGER account_matches_ledger"))
    try:
        with sessions() as session:
            report = reconcile(session)
            assert not report.consistent
            assert report.mismatched_accounts == 0
            assert report.projection_mismatched_accounts == 1
            assert report.projection_discrepancies[0].difference == 7
            assert session.get(Account, UUID(accounts[0])).ledger_balance == 10007
    finally:
        with sessions.begin() as session:
            session.execute(
                text("ALTER TABLE accounts DISABLE TRIGGER immutable_ledger_projection")
            )
            session.execute(
                text("UPDATE accounts SET ledger_balance = ledger_balance - 7 WHERE id = :id"),
                {"id": accounts[0]},
            )
            # The repair queued the still-enabled deferred balance check. Execute
            # it before ALTER TABLE, which rejects pending trigger events. This
            # validates the repaired state without disabling the accounting check.
            session.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
            session.execute(text("ALTER TABLE accounts ENABLE TRIGGER immutable_ledger_projection"))
    assert_projection(sessions)


def test_projection_migration_round_trip_preserves_funded_accounts(
    accounts, sessions, db_engine, monkeypatch
):
    config = migration_config(db_engine, monkeypatch)
    with sessions.begin() as session:
        transfer_money(session, TransferCreate(**payload(accounts, 23)), "before-migration")
        before = session.execute(text("SELECT id, balance FROM accounts ORDER BY id")).all()
        journal_before = session.execute(text("SELECT * FROM ledger_entries ORDER BY id")).all()
    command.downgrade(config, "0003")
    try:
        with db_engine.begin() as connection:
            with pytest.raises(IntegrityError, match="Balance must match journal"):
                with connection.begin_nested():
                    connection.execute(text("UPDATE accounts SET balance = balance + 1"))
                    connection.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
        command.upgrade(config, "head")
        with sessions() as session:
            assert (
                session.execute(text("SELECT id, balance FROM accounts ORDER BY id")).all()
                == before
            )
            assert (
                session.execute(text("SELECT * FROM ledger_entries ORDER BY id")).all()
                == journal_before
            )
        assert_projection(sessions)
        command.check(config)
    finally:
        command.upgrade(config, "head")


def test_projection_migration_refuses_existing_discrepancies(
    accounts, sessions, db_engine, monkeypatch
):
    config = migration_config(db_engine, monkeypatch)
    command.downgrade(config, "0003")
    with db_engine.begin() as connection:
        connection.execute(text("ALTER TABLE accounts DISABLE TRIGGER account_matches_ledger"))
        connection.execute(
            text("UPDATE accounts SET balance = balance + 7 WHERE id = :id"), {"id": accounts[0]}
        )
        connection.execute(text("ALTER TABLE accounts ENABLE TRIGGER account_matches_ledger"))
    try:
        with pytest.raises(IntegrityError, match="refusing projection migration"):
            command.upgrade(config, "head")
        with db_engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0003"
            assert (
                connection.scalar(
                    text("SELECT balance FROM accounts WHERE id = :id"), {"id": accounts[0]}
                )
                == 10007
            )
    finally:
        with db_engine.begin() as connection:
            connection.execute(
                text("UPDATE accounts SET balance = balance - 7 WHERE id = :id"),
                {"id": accounts[0]},
            )
        command.upgrade(config, "head")
    assert_projection(sessions)
