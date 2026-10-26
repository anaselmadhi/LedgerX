from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AccountCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    currency: Literal["EUR"] = "EUR"


class AccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    currency: str
    balance: int
    created_at: datetime


class BalanceRead(BaseModel):
    account_id: UUID
    currency: str
    balance: int


class AccountPage(BaseModel):
    items: list[AccountRead]
    next_after: UUID | None = None


class EntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    transaction_id: UUID
    account_id: UUID
    amount: int
    currency: str
    created_at: datetime


class HistoryRead(BaseModel):
    items: list[EntryRead]
    limit: int
    offset: int
    next_cursor: str | None = None
