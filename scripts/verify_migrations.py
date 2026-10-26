"""Destructive migration round trip restricted to the disposable _test database."""

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from alembic import command
from app.core.config import SCHEMA_REVISION, settings


def main():
    parsed = make_url(settings.database_url)
    if parsed.get_backend_name() != "postgresql" or not (parsed.database or "").endswith("_test"):
        raise SystemExit("Migration round trip requires a disposable PostgreSQL _test database")
    config = Config("alembic.ini")
    assert ScriptDirectory.from_config(config).get_current_head() == SCHEMA_REVISION
    engine = create_engine(settings.database_url)
    command.upgrade(config, "head")
    # The downgrade intentionally refuses to erase real reversal metadata or collapse
    # overlapping scoped keys. Only this explicit test command clears disposable data.
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE auth_tokens, idempotency_records, ledger_entries, "
                "transfers, accounts, users"
            )
        )
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    command.check(config)
    engine.dispose()
    print("Migration upgrade → downgrade → upgrade and ORM drift check passed.")


if __name__ == "__main__":
    main()
