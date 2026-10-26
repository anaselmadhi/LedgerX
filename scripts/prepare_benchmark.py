"""Provision demo admin only in a guarded _bench database (or isolated CI _test)."""

import os

from alembic.config import Config
from sqlalchemy import select
from sqlalchemy.engine import make_url

from alembic import command
from app.core.config import settings
from app.db.models import User
from app.db.session import SessionLocal
from app.schemas.auth import Credentials
from app.services.auth_service import register


def main() -> None:
    database = make_url(settings.database_url).database or ""
    allowed = database.endswith("_bench") or (
        os.getenv("CI") == "true" and database.endswith("_test")
    )
    if not allowed:
        raise SystemExit("Demo provisioning is restricted to _bench (or CI _test)")
    username = os.environ.get("BENCHMARK_USERNAME", "benchmark-admin")
    password = os.environ.get("BENCHMARK_PASSWORD")
    if not password:
        raise SystemExit("Set BENCHMARK_PASSWORD (local benchmark credentials only)")
    command.upgrade(Config("alembic.ini"), "head")
    with SessionLocal.begin() as session:
        existing = session.scalar(select(User).where(User.username == username))
        if existing is None:
            register(session, Credentials(username=username, password=password), admin=True)
        elif not existing.is_admin or not existing.is_active:
            raise SystemExit("Existing benchmark username is not an active administrator")
    print("Benchmark administrator available; existing passwords are not overwritten.")


if __name__ == "__main__":
    main()
