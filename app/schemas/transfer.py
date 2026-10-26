from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.db.models import MAX_AMOUNT

Amount = Annotated[int, Field(strict=True, gt=0, le=MAX_AMOUNT)]


class TransferCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_account_id: UUID
    destination_account_id: UUID
    amount: Amount
    currency: Literal["EUR"] = "EUR"

    @model_validator(mode="after")
    def distinct_accounts(self):
        if self.source_account_id == self.destination_account_id:
            raise ValueError("Source and destination must differ")
        return self


class FundingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    destination_account_id: UUID
    amount: Amount
    currency: Literal["EUR"] = "EUR"


class TransferRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    source_account_id: UUID
    destination_account_id: UUID
    amount: int
    currency: str
    created_at: datetime
    reversal_of: UUID | None = None
    reversal_reason: str | None = None


class ReversalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=200)

    @field_validator("reason")
    @classmethod
    def nonblank_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A nonblank reason is required")
        return value
