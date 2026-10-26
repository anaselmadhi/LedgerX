from app.core.config import settings
from app.db.models import SYSTEM_ACCOUNT_ID
from tests.test_security import register_customer


def test_session_profile_and_capabilities_follow_current_permissions(client, monkeypatch):
    profile = client.get("/auth/me")
    assert profile.status_code == 200
    assert profile.headers["cache-control"] == "no-store"
    assert profile.json()["username"] == "test-admin"
    assert profile.json()["dev_funding_enabled"] is True
    assert set(profile.json()) == {"id", "username", "is_admin", "dev_funding_enabled"}
    monkeypatch.setattr(settings, "enable_dev_funding", False)
    assert client.get("/auth/me").json()["dev_funding_enabled"] is False
    customer = register_customer(client, "web-customer")
    monkeypatch.setattr(settings, "enable_dev_funding", True)
    profile = client.get("/auth/me", headers=customer).json()
    assert profile["username"] == "web-customer"
    assert profile["is_admin"] is profile["dev_funding_enabled"] is False
    client.headers.pop("Authorization")
    assert client.get("/auth/me").status_code == 401
    assert client.get("/accounts").status_code == 401


def test_account_collection_is_bounded_paginated_and_owner_scoped(client, accounts):
    owner = register_customer(client, "web-owner")
    expected = sorted(
        client.post("/accounts", json={}, headers=owner).json()["id"] for _ in range(5)
    )
    page = client.get("/accounts?limit=2", headers=owner)
    assert page.headers["cache-control"] == "no-store"
    result = page.json()
    seen = [item["id"] for item in result["items"]]
    while result["next_after"]:
        result = client.get(
            "/accounts", params={"limit": 2, "after": result["next_after"]}, headers=owner
        ).json()
        seen.extend(item["id"] for item in result["items"])
    assert seen == expected
    assert str(SYSTEM_ACCOUNT_ID) not in seen
    assert not set(accounts) & set(seen)
    # Using another owner's UUID as the cursor cannot bypass the owner predicate.
    foreign_cursor = client.get("/accounts", params={"after": accounts[0]}, headers=owner).json()
    assert all(item["id"] in expected for item in foreign_cursor["items"])
    stranger = register_customer(client, "web-empty")
    assert client.get("/accounts", headers=stranger).json() == {"items": [], "next_after": None}
    for query in ("limit=0", "limit=101", "after=invalid"):
        assert client.get(f"/accounts?{query}", headers=owner).status_code == 422
