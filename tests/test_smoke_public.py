import io
import json

import pytest

from scripts import smoke_public


class Response(io.BytesIO):
    def __init__(self, path, body, status=200, headers=None):
        super().__init__(body)
        self.status = status
        self.url = "http://127.0.0.1:8000" + path
        self.headers = headers or {}


@pytest.mark.parametrize("schema", ["0003", None])
def test_smoke_rejects_stale_or_missing_schema(monkeypatch, schema):
    def get(url, **kwargs):
        path = url.removeprefix("http://127.0.0.1:8000")
        return Response(path, json.dumps({"status": "ok", "schema": schema}).encode())

    monkeypatch.setattr(smoke_public, "urlopen", get)
    with pytest.raises(RuntimeError, match="schema does not match"):
        smoke_public.check("http://127.0.0.1:8000", expected_schema="0004")


def test_smoke_checks_bundle_and_protected_routes_after_current_schema(monkeypatch):
    visited = []

    def get(url, **kwargs):
        path = url.removeprefix("http://127.0.0.1:8000")
        visited.append(path)
        if path.startswith("/health"):
            return Response(path, b'{"status":"ok","schema":"0004"}')
        if path == "/":
            return Response(
                path,
                b'<script src="/assets/main.js"></script>',
                headers={"content-security-policy": "default-src 'none'"},
            )
        if path == "/assets/main.js":
            return Response(path, b"/* built frontend */")
        return Response(path, b"{}", status=401)

    monkeypatch.setattr(smoke_public, "urlopen", get)
    smoke_public.check("http://127.0.0.1:8000", expected_schema="0004")
    assert "/assets/main.js" in visited
    assert set(visited[-4:]) == {"/auth/me", "/accounts", "/operations/reconciliation", "/metrics"}
