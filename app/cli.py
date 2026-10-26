"""Create a local administrator: python -m app.cli create-admin."""

import argparse
from getpass import getpass

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.core.exceptions import DomainError
from app.db.session import SessionLocal
from app.schemas.auth import Credentials
from app.services.auth_service import register


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["create-admin"])
    parser.parse_args(argv)
    username = input("Administrator username: ")
    password = getpass("Password (12–128 characters): ")
    if password != getpass("Confirm password: "):
        raise SystemExit("Passwords differ")
    try:
        credentials = Credentials(username=username, password=password)
    except ValidationError:
        raise SystemExit("Invalid username or password length") from None
    try:
        with SessionLocal.begin() as session:
            user = register(session, credentials, admin=True)
            user_id = user.id
    except DomainError as exc:
        raise SystemExit(exc.message) from None
    except SQLAlchemyError:
        raise SystemExit(
            "Database operation failed; verify database availability and migrations"
        ) from None
    print(f"Administrator created: {user_id}. Sign in with POST /auth/login.")


if __name__ == "__main__":
    main()
