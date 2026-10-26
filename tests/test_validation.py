from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.transfer import TransferCreate


@pytest.mark.parametrize("amount", [0, -1, 1.5, True, "12", 10**20])
def test_invalid_amount(amount):
    with pytest.raises(ValidationError):
        TransferCreate(source_account_id=uuid4(), destination_account_id=uuid4(), amount=amount)


def test_same_account():
    account = uuid4()
    with pytest.raises(ValidationError):
        TransferCreate(source_account_id=account, destination_account_id=account, amount=1)
