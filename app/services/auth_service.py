from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import DomainError
from app.core.security import (
    DUMMY_PASSWORD_HASH,
    hash_password,
    issue_token,
    token_digest,
    verify_password,
)
from app.db.models import AuthToken, User
from app.schemas.auth import Credentials, TokenRead


@dataclass(frozen=True)
class Principal:
    id: UUID
    username: str
    is_admin: bool
    token_hash: str


def register(session: Session, credentials: Credentials, *, admin: bool = False) -> User:
    encoded = hash_password(credentials.password.get_secret_value())
    user = session.scalar(
        insert(User)
        .values(
            username=credentials.username, password_hash=encoded, is_admin=admin, is_active=True
        )
        .on_conflict_do_nothing(index_elements=[User.username])
        .returning(User)
    )
    if user is None:
        raise DomainError("Username is unavailable", 409, "username_unavailable")
    return user


def login(session: Session, credentials: Credentials) -> TokenRead:
    user = session.scalar(select(User).where(User.username == credentials.username))
    encoded = user.password_hash if user is not None and user.is_active else DUMMY_PASSWORD_HASH
    valid = verify_password(credentials.password.get_secret_value(), encoded)
    if not valid or user is None or not user.is_active:
        raise DomainError("Invalid credentials", 401, "invalid_credentials")
    token, digest = issue_token()
    session.add(
        AuthToken(
            token_hash=digest,
            user_id=user.id,
            expires_at=datetime.now(UTC) + timedelta(seconds=settings.token_lifetime_seconds),
        )
    )
    session.flush()
    return TokenRead(access_token=token, expires_in=settings.token_lifetime_seconds)


def authenticate(session: Session, token: str) -> Principal:
    if len(token) != 43 or not token.isascii():
        raise DomainError("Invalid or expired token", 401, "invalid_token")
    digest = token_digest(token)
    user = session.scalar(
        select(User)
        .join(AuthToken, AuthToken.user_id == User.id)
        .where(
            AuthToken.token_hash == digest,
            AuthToken.revoked_at.is_(None),
            AuthToken.expires_at > func.now(),
            User.is_active.is_(True),
        )
    )
    if user is None:
        raise DomainError("Invalid or expired token", 401, "invalid_token")
    return Principal(user.id, user.username, user.is_admin, digest)


def logout(session: Session, principal: Principal) -> None:
    session.execute(
        update(AuthToken)
        .where(AuthToken.token_hash == principal.token_hash)
        .values(revoked_at=func.now())
    )
