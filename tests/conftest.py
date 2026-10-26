"""Integration tests deliberately require a disposable PostgreSQL database."""

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.core.config import settings


@pytest.fixture(scope="session")
def db_engine():
    from alembic.config import Config

    from alembic import command

    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.fail("Set TEST_DATABASE_URL to a disposable PostgreSQL database ending in _test")
    parsed = make_url(url)
    if parsed.get_backend_name() != "postgresql" or not (parsed.database or "").endswith("_test"):
        pytest.fail("Safety guard: tests require a PostgreSQL database ending in _test")
    engine = create_engine(
        url,
        pool_size=16,
        max_overflow=4,
        connect_args={"options": "-c lock_timeout=5000 -c statement_timeout=15000"},
    )
    previous = settings.database_url
    settings.database_url = url
    try:
        command.upgrade(Config("alembic.ini"), "head")
    finally:
        settings.database_url = previous
    yield engine
    engine.dispose()


@pytest.fixture()
def sessions(db_engine):
    # No enclosing transaction: worker connections must see committed data and real locks.
    with db_engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE auth_tokens, idempotency_records, ledger_entries, "
                "transfers, accounts, users"
            )
        )
        connection.execute(
            text("""
            INSERT INTO users (id, username, password_hash, is_admin, is_active) VALUES
                ('00000000-0000-0000-0000-000000000001', '_system', 'disabled', false, false),
                ('00000000-0000-0000-0000-000000000002', '_legacy', 'disabled', false, false)
        """)
        )
        connection.execute(
            text("""
            INSERT INTO accounts (id, currency, balance, is_system)
            VALUES ('00000000-0000-0000-0000-000000000001', 'EUR', 0, true)
        """)
        )
    return sessionmaker(db_engine, expire_on_commit=False)


@pytest.fixture()
def client(sessions, monkeypatch, test_password_hash):
    from fastapi.testclient import TestClient

    from app.core.auth_limits import AuthLimiter, get_auth_limiter
    from app.db.models import User
    from app.db.session import get_session
    from app.main import app

    def override_session():
        with sessions() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    # Each test gets a fresh limiter with real default bounds, rather than disabling it.
    limiter = AuthLimiter()
    app.dependency_overrides[get_auth_limiter] = lambda: limiter
    monkeypatch.setattr(settings, "enable_dev_funding", True)
    with sessions.begin() as session:
        session.add(User(username="test-admin", password_hash=test_password_hash, is_admin=True))
    try:
        with TestClient(app, raise_server_exceptions=False) as test_client:
            login = test_client.post(
                "/auth/login", json={"username": "test-admin", "password": "test-password-123"}
            )
            assert login.status_code == 200, login.text
            test_client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def test_password_hash():
    from app.core.security import hash_password

    return hash_password("test-password-123")


def pytest_collection_modifyitems(items):
    for item in items:
        if {"db_engine", "sessions", "client", "accounts"} & set(item.fixturenames):
            item.add_marker(pytest.mark.integration)


@pytest.fixture()
def accounts(client):
    first = client.post("/accounts", json={}).json()["id"]
    second = client.post("/accounts", json={}).json()["id"]
    result = client.post("/dev/funding", json={"destination_account_id": first, "amount": 10000})
    assert result.status_code == 201, result.text
    return first, second


def payload(accounts, amount=1000):
    return {
        "source_account_id": accounts[0],
        "destination_account_id": accounts[1],
        "amount": amount,
        "currency": "EUR",
    }
