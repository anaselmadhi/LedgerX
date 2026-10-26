import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.core.config import settings


def migration_config(db_engine, monkeypatch):
    from alembic.config import Config

    monkeypatch.setattr(
        settings, "database_url", db_engine.url.render_as_string(hide_password=False)
    )
    return Config("alembic.ini")


def test_upgrade_preserves_legacy_money_and_quarantines_ownership(sessions, db_engine, monkeypatch):
    from alembic import command

    config = migration_config(db_engine, monkeypatch)
    command.downgrade(config, "0001")
    try:
        with db_engine.begin() as connection:
            connection.execute(
                text("""
                INSERT INTO accounts (id, currency, balance, is_system)
                VALUES ('11111111-1111-1111-1111-111111111111', 'EUR', 7, false);
                UPDATE accounts SET balance = -7
                WHERE id = '00000000-0000-0000-0000-000000000001';
                INSERT INTO transfers
                    (id, source_account_id, destination_account_id, amount, currency)
                VALUES ('22222222-2222-2222-2222-222222222222',
                    '00000000-0000-0000-0000-000000000001',
                    '11111111-1111-1111-1111-111111111111', 7, 'EUR');
                INSERT INTO ledger_entries (id, transaction_id, account_id, amount, currency) VALUES
                    ('33333333-3333-3333-3333-333333333333',
                     '22222222-2222-2222-2222-222222222222',
                     '00000000-0000-0000-0000-000000000001', -7, 'EUR'),
                    ('44444444-4444-4444-4444-444444444444',
                     '22222222-2222-2222-2222-222222222222',
                     '11111111-1111-1111-1111-111111111111', 7, 'EUR');
                INSERT INTO idempotency_records (key, fingerprint, transaction_id)
                VALUES ('legacy-key', repeat('a', 64), '22222222-2222-2222-2222-222222222222');
            """)
            )
        command.upgrade(config, "head")
        with db_engine.connect() as connection:
            account = connection.execute(
                text("""
                SELECT balance, owner_id FROM accounts
                WHERE id = '11111111-1111-1111-1111-111111111111'
            """)
            ).one()
            assert account.balance == 7
            assert str(account.owner_id) == "00000000-0000-0000-0000-000000000002"
            assert connection.scalar(text("SELECT count(*) FROM ledger_entries")) == 2
            assert (
                connection.scalar(text("SELECT is_active FROM users WHERE username = '_legacy'"))
                is False
            )
            assert (
                connection.scalar(text("SELECT fingerprint FROM idempotency_records")) == "a" * 64
            )
        command.check(config)
    finally:
        command.upgrade(config, "head")


def test_downgrade_refuses_to_discard_active_authentication(client, db_engine, monkeypatch):
    from alembic import command

    config = migration_config(db_engine, monkeypatch)
    with pytest.raises(DBAPIError, match="refusing lossy downgrade"):
        command.downgrade(config, "0002")
    with db_engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0004"
        assert connection.scalar(text("SELECT count(*) FROM users WHERE is_admin")) == 1
