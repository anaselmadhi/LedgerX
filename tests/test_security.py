from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.security import token_digest
from app.db.models import AuthToken, User
from tests.conftest import payload


def register_customer(client, name):
    credentials = {"username": name, "password": "customer-password-123"}
    response = client.post("/auth/register", json=credentials)
    assert response.status_code == 201, response.text
    assert response.json()["is_admin"] is False
    assert "password" not in response.text
    login = client.post("/auth/login", json=credentials)
    assert login.status_code == 200
    assert login.headers["cache-control"] == "no-store"
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_authentication_required_and_passwords_not_echoed(client):
    client.headers.pop("Authorization")
    response = client.post("/accounts", json={})
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    for path in ("/operations/reconciliation", "/metrics"):
        assert client.get(path).status_code == 401
    invalid = client.post("/auth/register", json={"username": "user", "password": "secret"})
    assert invalid.status_code == 422
    assert "secret" not in invalid.text
    assert (
        client.post(
            "/auth/register",
            json={
                "username": "evil",
                "password": "long-enough-password",
                "is_admin": True,
            },
        ).status_code
        == 422
    )


def test_ownership_and_privilege_boundaries(client, accounts):
    stranger = register_customer(client, "stranger")
    for suffix in ("", "/balance", "/transactions"):
        assert client.get(f"/accounts/{accounts[0]}{suffix}", headers=stranger).status_code == 404
    assert client.post("/transfers", json=payload(accounts), headers=stranger).status_code == 404
    assert (
        client.post(
            "/dev/funding",
            json={
                "destination_account_id": accounts[0],
                "amount": 1,
            },
            headers=stranger,
        ).status_code
        == 403
    )
    assert client.get("/operations/reconciliation", headers=stranger).status_code == 403
    assert client.get("/metrics", headers=stranger).status_code == 403
    transfer = client.post(
        "/transfers", json=payload(accounts), headers={"Idempotency-Key": "private-payment"}
    ).json()
    assert client.get(f"/transfers/{transfer['id']}", headers=stranger).status_code == 404
    assert (
        client.post(
            f"/transfers/{transfer['id']}/reversal", json={"reason": "Theft"}, headers=stranger
        ).status_code
        == 404
    )
    # A leaked key cannot retrieve another customer's completed response.
    assert (
        client.post(
            "/transfers",
            json=payload(accounts),
            headers=stranger | {"Idempotency-Key": "private-payment"},
        ).status_code
        == 404
    )


def test_only_recipient_can_refund_cross_owner_transfer(client, accounts):
    recipient = register_customer(client, "recipient")
    target = client.post("/accounts", json={}, headers=recipient).json()["id"]
    transfer = client.post("/transfers", json=payload((accounts[0], target), 1000)).json()
    path = f"/transfers/{transfer['id']}/reversal"
    assert client.post(path, json={"reason": "Unauthorized clawback"}).status_code == 404
    assert client.get(f"/transfers/{transfer['id']}", headers=recipient).status_code == 200
    refund = client.post(
        path, json={"reason": "Return payment"}, headers=recipient | {"Idempotency-Key": "refund"}
    )
    assert refund.status_code == 201, refund.text
    assert client.get(f"/accounts/{accounts[0]}/balance").json()["balance"] == 10000


def test_expired_revoked_and_disabled_tokens_are_rejected(client, sessions):
    headers = register_customer(client, "token-user")
    assert client.post("/accounts", json={}, headers=headers).status_code == 201
    assert client.post("/auth/logout", headers=headers).status_code == 204
    assert client.post("/accounts", json={}, headers=headers).status_code == 401
    credentials = {"username": "token-user", "password": "customer-password-123"}
    token = client.post("/auth/login", json=credentials).json()["access_token"]
    with sessions.begin() as session:
        session.get(AuthToken, token_digest(token)).expires_at = datetime.now(UTC) - timedelta(
            seconds=1
        )
    assert (
        client.post("/accounts", json={}, headers={"Authorization": f"Bearer {token}"}).status_code
        == 401
    )
    token = client.post("/auth/login", json=credentials).json()["access_token"]
    with sessions.begin() as session:
        user = session.scalar(select(User).where(User.username == "token-user"))
        user.is_active = False
    assert (
        client.post("/accounts", json={}, headers={"Authorization": f"Bearer {token}"}).status_code
        == 401
    )
    assert client.post("/auth/login", json=credentials).status_code == 401


def test_wrong_credentials_generic_errors_and_token_hash_storage(client, sessions):
    register_customer(client, "customer")
    wrong = client.post(
        "/auth/login", json={"username": "customer", "password": "wrong-password-123"}
    )
    unknown = client.post(
        "/auth/login", json={"username": "unknown", "password": "wrong-password-123"}
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["detail"] == unknown.json()["detail"] == "Invalid credentials"
    with sessions() as session:
        user = session.scalar(select(User).where(User.username == "customer"))
        assert user.password_hash.startswith("scrypt$")
        assert user.password_hash != "customer-password-123"
        assert all(len(token.token_hash) == 64 for token in session.scalars(select(AuthToken)))


def test_idempotency_keys_are_scoped_to_the_authenticated_user(client):
    ids = []
    for name in ("alice", "bob"):
        headers = register_customer(client, name)
        source = client.post("/accounts", json={}, headers=headers).json()["id"]
        target = client.post("/accounts", json={}, headers=headers).json()["id"]
        assert (
            client.post(
                "/dev/funding",
                json={
                    "destination_account_id": source,
                    "amount": 100,
                },
            ).status_code
            == 201
        )
        result = client.post(
            "/transfers",
            json=payload((source, target), 10),
            headers=headers | {"Idempotency-Key": "same-customer-key"},
        )
        assert result.status_code == 201
        ids.append(result.json()["id"])
    assert len(set(ids)) == 2
