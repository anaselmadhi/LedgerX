"""Create an administrator on the chosen hosted database, without shell-history secrets."""

import os
from getpass import getpass


def main() -> None:
    database_url = getpass("Remote direct PostgreSQL URL (hidden; TLS required): ").strip()
    if not database_url:
        raise SystemExit("No URL supplied; nothing changed.")
    # Set the URL before importing the application engine. Never rewrite the local .env.
    os.environ["DATABASE_URL"] = database_url
    os.environ["PUBLIC_DEMO"] = "true"
    try:
        from app.core.config import settings
        from app.start import public_database_error
    except (ValueError, TypeError):
        raise SystemExit("Invalid configuration; nothing changed.") from None
    if error := public_database_error(settings):
        raise SystemExit(error)

    from app.cli import main as create_admin

    create_admin(["create-admin"])


if __name__ == "__main__":
    main()
