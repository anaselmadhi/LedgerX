import base64
import binascii
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, ValidationError

from app.core.exceptions import DomainError


class HistoryCursor(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[1] = 1
    account_id: UUID
    created_at: AwareDatetime
    entry_id: UUID

    def encode(self) -> str:
        return base64.urlsafe_b64encode(self.model_dump_json().encode()).decode().rstrip("=")

    @classmethod
    def decode(cls, value: str, account_id: UUID) -> "HistoryCursor":
        try:
            decoded = base64.b64decode(
                value + "=" * (-len(value) % 4), altchars=b"-_", validate=True
            )
            cursor = cls.model_validate_json(decoded)
            if cursor.account_id != account_id:
                raise ValueError("Cursor belongs to another account")
        except (ValueError, binascii.Error, ValidationError) as exc:
            raise DomainError("Invalid history cursor", 422, "invalid_cursor") from exc
        return cursor


def encode_cursor(account_id: UUID, created_at: datetime, entry_id: UUID) -> str:
    return HistoryCursor(account_id=account_id, created_at=created_at, entry_id=entry_id).encode()
