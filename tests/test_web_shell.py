from fastapi.testclient import TestClient

from app.api import web
from app.main import app


def test_frontend_missing_build_has_actionable_response(tmp_path, monkeypatch):
    monkeypatch.setattr(web, "DIST", tmp_path)
    with TestClient(app) as browser:
        response = browser.get("/")
        assert response.status_code == 503
        assert "scripts/frontend.sh build" in response.text
        assert browser.get("/health/live").status_code == 200


def test_frontend_shell_headers_and_api_routes(tmp_path, monkeypatch):
    (tmp_path / "index.html").write_text('<!doctype html><div id="root"></div>')
    monkeypatch.setattr(web, "DIST", tmp_path)
    with TestClient(app) as browser:
        response = browser.get("/")
        assert response.status_code == 200
        assert 'id="root"' in response.text
        assert response.headers["cache-control"] == "no-store"
        assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
        assert "'unsafe-inline'" not in response.headers["content-security-policy"]
        assert browser.get("/openapi.json").status_code == 200
        assert browser.get("/unrecognised").status_code == 404
