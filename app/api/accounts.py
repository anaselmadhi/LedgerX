from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response

from app.api.dependencies import DB, CurrentUser
from app.schemas.account import AccountCreate, AccountPage, AccountRead, BalanceRead, HistoryRead
from app.services import account_service

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=AccountPage)
def list_accounts(
    session: DB,
    principal: CurrentUser,
    response: Response,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    after: UUID | None = None,
):
    response.headers["Cache-Control"] = "no-store"
    return account_service.list_accounts(session, principal.id, limit, after)


@router.post("", response_model=AccountRead, status_code=201)
def create_account(body: AccountCreate, session: DB, principal: CurrentUser):
    with session.begin():
        return account_service.create_account(session, body.currency, principal.id)


@router.get("/{account_id}", response_model=AccountRead)
def get_account(account_id: UUID, session: DB, principal: CurrentUser):
    return account_service.get_account(session, account_id, principal.id)


@router.get("/{account_id}/balance", response_model=BalanceRead)
def balance(account_id: UUID, session: DB, principal: CurrentUser):
    account = account_service.get_account(session, account_id, principal.id)
    return BalanceRead(account_id=account.id, currency=account.currency, balance=account.balance)


@router.get("/{account_id}/transactions", response_model=HistoryRead)
def history(
    account_id: UUID,
    session: DB,
    principal: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, deprecated=True)] = 0,
    cursor: Annotated[str | None, Query(min_length=1, max_length=512)] = None,
):
    return account_service.history(session, account_id, limit, offset, cursor, principal.id)
