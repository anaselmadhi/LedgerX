from uuid import UUID

from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session

from app.core.cursor import HistoryCursor, encode_cursor
from app.core.exceptions import DomainError
from app.db.models import SYSTEM_USER_ID, Account, LedgerEntry
from app.schemas.account import AccountPage, HistoryRead


def list_accounts(
    session: Session, owner_id: UUID, limit: int, after: UUID | None = None
) -> AccountPage:
    query = select(Account).where(Account.owner_id == owner_id, Account.is_system.is_(False))
    if after is not None:
        query = query.where(Account.id > after)
    accounts = session.scalars(query.order_by(Account.id).limit(limit + 1)).all()
    page = accounts[:limit]
    return AccountPage(items=page, next_after=page[-1].id if len(accounts) > limit else None)


def create_account(session: Session, currency: str, owner_id: UUID = SYSTEM_USER_ID) -> Account:
    account = Account(currency=currency, owner_id=owner_id)
    session.add(account)
    session.flush()
    return account


def get_account(session: Session, account_id: UUID, owner_id: UUID | None = None) -> Account:
    account = session.get(Account, account_id)
    if (
        account is None
        or account.is_system
        or (owner_id is not None and account.owner_id != owner_id)
    ):
        raise DomainError("Account not found", 404, "account_not_found")
    return account


def history(
    session: Session,
    account_id: UUID,
    limit: int,
    offset: int = 0,
    cursor: str | None = None,
    owner_id: UUID | None = None,
) -> HistoryRead:
    get_account(session, account_id, owner_id)
    query = select(LedgerEntry).where(LedgerEntry.account_id == account_id)
    if cursor is not None:
        if offset:
            raise DomainError("Use cursor or offset, not both", 422, "invalid_pagination")
        position = HistoryCursor.decode(cursor, account_id)
        query = query.where(
            tuple_(LedgerEntry.created_at, LedgerEntry.id)
            < tuple_(position.created_at, position.entry_id)
        )
    entries = session.scalars(
        query.order_by(LedgerEntry.created_at.desc(), LedgerEntry.id.desc())
        .limit(limit + 1)
        .offset(offset)
    ).all()
    page = entries[:limit]
    next_cursor = None
    if len(entries) > limit:
        last = page[-1]
        next_cursor = encode_cursor(account_id, last.created_at, last.id)
    return HistoryRead(items=page, limit=limit, offset=offset, next_cursor=next_cursor)
