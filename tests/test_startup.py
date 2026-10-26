from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.start import public_database_error, server_port


def test_provider_urls_select_psycopg3_and_keep_tls_parameters():
    for scheme in ("postgres", "postgresql", "postgresql+psycopg"):
        config = Settings(
            _env_file=None,
            database_url=f"{scheme}://demo:example%40password@db.example/demo?sslmode=require",
        )
        assert config.database_url.startswith("postgresql+psycopg://")
        assert "example%40password" in config.database_url
        assert config.database_url.endswith("sslmode=require")


def test_invalid_database_configuration_does_not_print_secrets():
    for url in ("sqlite:///secret-database", "secret-invalid-url"):
        with pytest.raises(ValidationError) as error:
            Settings(_env_file=None, database_url=url)
        assert url not in str(error.value)


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://demo:secret@localhost/demo?sslmode=require",
        "postgresql://demo:ledgerx_local@db.example/demo?sslmode=require",
        "postgresql://demo:secret@db.example/demo",
        "postgresql://demo:secret@db.example/demo?sslmode=prefer",
        "postgresql://demo:secret@db-pooler.example/demo?sslmode=require",
    ],
)
def test_public_startup_rejects_unsafe_database_configuration(url):
    config = Settings(_env_file=None, public_demo=True, database_url=url)
    assert public_database_error(config)


def test_public_startup_accepts_direct_tls_database_and_local_mode_remains_available():
    config = Settings(
        _env_file=None,
        public_demo=True,
        database_url="postgresql://demo:secret@db.example/demo?sslmode=require",
    )
    assert public_database_error(config) is None
    config = Settings(_env_file=None, public_demo=False)
    assert public_database_error(config) is None


@pytest.mark.parametrize("value", ["0", "65536", "-1", "abc", "8000; echo secret"])
def test_invalid_ports_are_rejected_without_shell_evaluation(value):
    with pytest.raises(ValueError):
        server_port(value)


def test_container_startup_migrates_then_honors_provider_port(monkeypatch):
    from app import start

    calls = []
    monkeypatch.setenv("PORT", "10000")
    monkeypatch.setattr(start, "settings", Settings(_env_file=None, public_demo=False))
    monkeypatch.setattr(start.command, "upgrade", lambda *_: calls.append("migration"))

    def run(app, **kwargs):
        calls.append("server")
        assert app == "app.main:app"
        assert kwargs["port"] == 10000
        assert kwargs["host"] == "0.0.0.0"
        assert kwargs["workers"] == 1
        assert kwargs["proxy_headers"] is False

    monkeypatch.setattr(start.uvicorn, "run", run)
    start.main()
    assert calls == ["migration", "server"]


def test_failed_migration_does_not_start_api_or_leak_exception(monkeypatch, capsys):
    from app import start

    monkeypatch.setattr(start, "settings", Settings(_env_file=None, public_demo=False))
    monkeypatch.setattr(start.command, "upgrade", Mock(side_effect=RuntimeError("secret-value")))
    server = Mock()
    monkeypatch.setattr(start.uvicorn, "run", server)
    with pytest.raises(SystemExit):
        start.main()
    server.assert_not_called()
    output = capsys.readouterr()
    assert "secret-value" not in output.err
    assert "Migration failed" in output.err
