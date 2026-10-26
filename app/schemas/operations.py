from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class BalanceDiscrepancy(BaseModel):
    account_id: UUID
    stored_balance: int
    journal_balance: int
    difference: int


class ReconciliationRead(BaseModel):
    checked_at: datetime
    consistent: bool
    account_count: int
    transfer_count: int
    entry_count: int
    mismatched_accounts: int
    projection_mismatched_accounts: int
    invalid_transfers: int
    total_balance: int
    ledger_total: int
    discrepancies: list[BalanceDiscrepancy]
    projection_discrepancies: list[BalanceDiscrepancy]
    discrepancy_sample_limit: int = 100
