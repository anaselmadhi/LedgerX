"""Single-process container entry point, with migrations and safe startup errors."""

import os
import sys

import uvicorn
from alembic.config import Config
from sqlalchemy.engine import make_url

from alembic import command
from app.core.config import Settings, settings


def public_database_error(config: Settings) -> str | None:
    if not config.public_demo:
        return None
    url = make_url(config.database_url)
    if not url.host or url.host in {"localhost", "127.0.0.1", "::1", "db"}:
        return "PUBLIC_DEMO requires a remote PostgreSQL database."
    if not url.password or url.password == "ledgerx_local":
        return "PUBLIC_DEMO requires database credentials distinct from the local demo."
    if url.query.get("sslmode") not in {"require", "verify-ca", "verify-full"}:
        return "PUBLIC_DEMO requires PostgreSQL TLS (sslmode=require or verification enabled)."
    if "-pooler" in url.host:
        return "Use the direct PostgreSQL endpoint for startup migrations and session settings."
    return None


def server_port(value: str) -> int:
    try:
        port = int(value)
    except ValueError:
        raise ValueError("PORT must be an integer between 1 and 65535") from None
    if not 1 <= port <= 65535:
        raise ValueError("PORT must be an integer between 1 and 65535")
    return port


def main() -> None:
    try:
        port = server_port(os.environ.get("PORT", "8000"))
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    if error := public_database_error(settings):
        raise SystemExit(error)
    try:
        command.upgrade(Config("alembic.ini"), "head")
    except Exception as exc:
        # SQLAlchemy exceptions may include credentials, SQL parameters or URLs.
        print(
            f"Migration failed ({type(exc).__name__}). Check database access and schema; "
            "the API was not started.",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        workers=1,
        access_log=False,
        proxy_headers=False,
    )


if __name__ == "__main__":
    main()
