from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.core.cursor import HistoryCursor, encode_cursor
from app.core.exceptions import DomainError


def test_cursor_round_trip():
    account, entry, timestamp = uuid4(), uuid4(), datetime.now(UTC)
    decoded = HistoryCursor.decode(encode_cursor(account, timestamp, entry), account)
    assert (decoded.account_id, decoded.created_at, decoded.entry_id) == (account, timestamp, entry)


@pytest.mark.parametrize("cursor", ["", "%%%", "e30", "Zm9v", "é", "a"])
def test_invalid_cursor(cursor):
    with pytest.raises(DomainError) as error:
        HistoryCursor.decode(cursor, uuid4())
    assert error.value.status_code == 422


def test_cursor_cannot_be_reused_for_another_account():
    cursor = encode_cursor(uuid4(), datetime.now(UTC), uuid4())
    with pytest.raises(DomainError):
        HistoryCursor.decode(cursor, uuid4())
