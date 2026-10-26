from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.operations import ReconciliationRead

# One statement => one MVCC snapshot. Separate SELECTs could incorrectly report
# drift when a transfer commits between the balance and journal reads.
RECONCILIATION_SQL = text("""
    WITH account_totals AS (
        SELECT account_id, sum(amount) AS total FROM ledger_entries GROUP BY account_id
    ), mismatches AS (
        SELECT a.id AS account_id, a.balance AS stored_balance,
            coalesce(e.total, 0) AS journal_balance,
            a.balance - coalesce(e.total, 0) AS difference
        FROM accounts a LEFT JOIN account_totals e ON e.account_id = a.id
        WHERE a.balance <> coalesce(e.total, 0)
    ), projection_mismatches AS (
        SELECT a.id AS account_id, a.ledger_balance AS stored_balance,
            coalesce(e.total, 0) AS journal_balance,
            a.ledger_balance - coalesce(e.total, 0) AS difference
        FROM accounts a LEFT JOIN account_totals e ON e.account_id = a.id
        WHERE a.ledger_balance <> coalesce(e.total, 0)
    ), transfer_totals AS (
        SELECT t.id, count(e.id) AS n,
               count(e.id) FILTER (WHERE e.currency = t.currency AND (
                   (e.account_id = t.source_account_id AND e.amount = -t.amount) OR
                   (e.account_id = t.destination_account_id AND e.amount = t.amount)
               )) AS valid
        FROM transfers t LEFT JOIN ledger_entries e ON e.transaction_id = t.id
        GROUP BY t.id
    )
    SELECT
        statement_timestamp() AS checked_at,
        (SELECT count(*) FROM accounts) AS account_count,
        (SELECT count(*) FROM transfers) AS transfer_count,
        (SELECT count(*) FROM ledger_entries) AS entry_count,
        (SELECT count(*) FROM mismatches) AS mismatched_accounts,
        (SELECT count(*) FROM projection_mismatches) AS projection_mismatched_accounts,
        coalesce((SELECT jsonb_agg(to_jsonb(sample)) FROM (
            SELECT * FROM mismatches ORDER BY account_id LIMIT 100
        ) sample), '[]'::jsonb) AS discrepancies,
        coalesce((SELECT jsonb_agg(to_jsonb(sample)) FROM (
            SELECT * FROM projection_mismatches ORDER BY account_id LIMIT 100
        ) sample), '[]'::jsonb) AS projection_discrepancies,
        (SELECT count(*) FROM transfer_totals WHERE n <> 2 OR valid <> 2) AS invalid_transfers,
        (SELECT coalesce(sum(balance), 0) FROM accounts) AS total_balance,
        (SELECT coalesce(sum(amount), 0) FROM ledger_entries) AS ledger_total
""")


def reconcile(session: Session) -> ReconciliationRead:
    row = session.execute(RECONCILIATION_SQL).mappings().one()
    consistent = (
        row["mismatched_accounts"] == 0
        and row["projection_mismatched_accounts"] == 0
        and row["invalid_transfers"] == 0
        and row["total_balance"] == 0
        and row["ledger_total"] == 0
    )
    return ReconciliationRead(consistent=consistent, **row)
