from typing import Annotated

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError
from app.db.session import get_session
from app.services.auth_service import Principal, authenticate

DB = Annotated[Session, Depends(get_session)]
IdempotencyKey = Annotated[
    str | None, Header(min_length=1, max_length=128, pattern=r"^[\x21-\x7E]+$")
]
bearer = HTTPBearer(auto_error=False)


def current_user(
    session: DB,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> Principal:
    if credentials is None:
        raise DomainError("Bearer authentication required", 401, "authentication_required")
    # End the auth read transaction before the route opens its business transaction.
    with session.begin():
        return authenticate(session, credentials.credentials)


CurrentUser = Annotated[Principal, Depends(current_user)]


def require_admin(principal: CurrentUser) -> Principal:
    if not principal.is_admin:
        raise DomainError("Administrator access required", 403, "admin_required")
    return principal


AdminUser = Annotated[Principal, Depends(require_admin)]
