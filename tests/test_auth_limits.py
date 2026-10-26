from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.auth_limits import AuthLimiter, auth_attempt, get_auth_limiter


def test_sliding_window_expiry_and_shared_peer_budget():
    now = [0.0]
    limiter = AuthLimiter(per_peer=2, window_seconds=60, clock=lambda: now[0])
    assert limiter.acquire("alice") is None
    limiter.release()
    now[0] = 20
    assert limiter.acquire("alice") is None
    limiter.release()
    now[0] = 20.1
    assert limiter.acquire("alice") == 40
    assert limiter.acquire("bob") is None
    limiter.release()
    now[0] = 60
    assert limiter.acquire("alice") is None
    limiter.release()
    assert limiter.acquire("alice") == 20


def test_rotating_peers_cannot_bypass_global_budget():
    now = [0.0]
    limiter = AuthLimiter(total=3, clock=lambda: now[0])
    for peer in ("one", "two", "three"):
        assert limiter.acquire(peer) is None
        limiter.release()
    for i in range(1000):
        assert limiter.acquire(f"rotating-{i}") == 60
    assert len(limiter._events) == len(limiter._counts) == 3
    now[0] = 60
    assert limiter.acquire("new") is None
    limiter.release()
    assert len(limiter._events) == len(limiter._counts) == 1


def test_threaded_requests_cannot_overbook_hashing_slots():
    limiter = AuthLimiter(concurrent=2)
    barrier = Barrier(16)

    def reserve(index):
        barrier.wait(timeout=5)
        return limiter.acquire(str(index))

    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(reserve, range(16)))
    assert results.count(None) == 2
    assert results.count(1) == 14
    limiter.release()
    limiter.release()
    assert limiter.acquire("after-completion") is None
    limiter.release()


def test_invalid_limits_and_unbalanced_release_are_rejected():
    with pytest.raises(ValueError):
        AuthLimiter(total=0)
    with pytest.raises(RuntimeError):
        AuthLimiter().release()


def test_http_throttle_ignores_spoofed_headers_and_releases_after_errors():
    app = FastAPI()
    limiter = AuthLimiter(per_peer=2, concurrent=1)
    app.dependency_overrides[get_auth_limiter] = lambda: limiter
    reached = []

    @app.post("/auth/login", dependencies=[Depends(auth_attempt)])
    def login():
        reached.append("login")
        raise HTTPException(status_code=401, detail="Invalid credentials")

    @app.post("/auth/register", dependencies=[Depends(auth_attempt)])
    def register():
        reached.append("register")
        return {"created": True}

    @app.get("/health/live")
    def live():
        return {"status": "ok"}

    with TestClient(app) as browser:
        assert browser.post("/auth/login").status_code == 401
        assert browser.post("/auth/register").status_code == 200
        response = browser.post(
            "/auth/login",
            headers={"X-Forwarded-For": "different-ip", "CF-Connecting-IP": "another-ip"},
        )
        assert response.status_code == 429
        assert 1 <= int(response.headers["retry-after"]) <= 60
        assert response.headers["cache-control"] == "no-store"
        assert reached == ["login", "register"]
        assert browser.get("/health/live").status_code == 200


def test_actual_auth_routes_reject_before_password_work(monkeypatch):
    from app.db.session import get_session
    from app.main import app
    from app.services import auth_service

    limiter = AuthLimiter(total=1)
    assert limiter.acquire("used-budget") is None
    limiter.release()
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_auth_limiter] = lambda: limiter

    def no_database():
        yield None

    def password_work(*args, **kwargs):
        pytest.fail("Throttled requests must not reach authentication services")

    app.dependency_overrides[get_session] = no_database
    monkeypatch.setattr(auth_service, "login", password_work)
    monkeypatch.setattr(auth_service, "register", password_work)
    try:
        with TestClient(app) as browser:
            for path in ("/auth/login", "/auth/register"):
                response = browser.post(
                    path, json={"username": "someone", "password": "a-valid-long-password"}
                )
                assert response.status_code == 429
                assert "x-request-id" in response.headers
                assert "a-valid-long-password" not in response.text
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
