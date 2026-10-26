"""Maintain the journal total incrementally; retain deferred balance validation."""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    # Hold writers out while validating/backfilling. Any discrepancy aborts the
    # whole migration: a migration must never silently repair financial balances.
    op.execute("""
        LOCK TABLE accounts, transfers, ledger_entries IN ACCESS EXCLUSIVE MODE;
        DO $$ BEGIN
            IF EXISTS (
                SELECT 1 FROM accounts a LEFT JOIN (
                    SELECT account_id, sum(amount) AS total
                    FROM ledger_entries GROUP BY account_id
                ) e ON e.account_id = a.id
                WHERE a.balance IS DISTINCT FROM coalesce(e.total, 0)
            ) THEN
                RAISE EXCEPTION 'Ledger discrepancy; refusing projection migration'
                    USING ERRCODE = '23514';
            END IF;
        END; $$;

        ALTER TABLE accounts ADD COLUMN ledger_balance NUMERIC NOT NULL DEFAULT 0;

        CREATE OR REPLACE FUNCTION check_account_balance() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE target UUID; actual BIGINT; expected NUMERIC;
        BEGIN
            IF TG_TABLE_NAME = 'accounts' THEN target := NEW.id;
            ELSE target := NEW.account_id; END IF;
            SELECT balance, ledger_balance INTO actual, expected
                FROM public.accounts WHERE id = target;
            IF actual IS DISTINCT FROM expected THEN
                RAISE EXCEPTION 'Balance must match journal' USING ERRCODE = '23514';
            END IF;
            RETURN NULL;
        END; $$;

        UPDATE accounts a SET ledger_balance = e.total
        FROM (SELECT account_id, sum(amount) AS total FROM ledger_entries GROUP BY account_id) e
        WHERE e.account_id = a.id;
        SET CONSTRAINTS ALL IMMEDIATE;
        SET CONSTRAINTS ALL DEFERRED;

        CREATE FUNCTION protect_ledger_projection() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                IF NEW.ledger_balance IS DISTINCT FROM 0::numeric THEN
                    RAISE EXCEPTION 'Journal projection starts at zero' USING ERRCODE = '23514';
                END IF;
            ELSIF NEW.ledger_balance IS DISTINCT FROM OLD.ledger_balance
                  AND pg_trigger_depth() <> 2 THEN
                RAISE EXCEPTION 'Journal projection is maintained by ledger inserts'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END; $$;
        CREATE TRIGGER immutable_ledger_projection BEFORE INSERT OR UPDATE ON accounts
            FOR EACH ROW EXECUTE FUNCTION protect_ledger_projection();

        CREATE FUNCTION project_inserted_entries() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE delta RECORD;
        BEGIN
            -- The transition relation contains only rows actually inserted by this
            -- statement (including COPY, excluding ON CONFLICT DO NOTHING rows).
            -- UUID order agrees with the service's account lock order.
            FOR delta IN
                SELECT account_id, sum(amount) AS amount FROM inserted_entries
                GROUP BY account_id ORDER BY account_id
            LOOP
                UPDATE public.accounts SET ledger_balance = ledger_balance + delta.amount
                    WHERE id = delta.account_id;
            END LOOP;
            RETURN NULL;
        END; $$;
        CREATE TRIGGER project_ledger_inserts AFTER INSERT ON ledger_entries
            REFERENCING NEW TABLE AS inserted_entries
            FOR EACH STATEMENT EXECUTE FUNCTION project_inserted_entries();
    """)


def downgrade():
    # Restoring the original full-history validator is lossless. Do not touch
    # balances, journal entries, transfer metadata or idempotency records.
    op.execute("""
        LOCK TABLE accounts, transfers, ledger_entries IN ACCESS EXCLUSIVE MODE;
        SET CONSTRAINTS ALL IMMEDIATE;
        DROP TRIGGER project_ledger_inserts ON ledger_entries;
        DROP TRIGGER immutable_ledger_projection ON accounts;
        DROP FUNCTION project_inserted_entries(), protect_ledger_projection();
        CREATE OR REPLACE FUNCTION check_account_balance() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE target UUID; actual BIGINT; expected NUMERIC;
        BEGIN
            IF TG_TABLE_NAME = 'accounts' THEN target := NEW.id;
            ELSE target := NEW.account_id; END IF;
            SELECT balance INTO actual FROM public.accounts WHERE id = target;
            SELECT coalesce(sum(amount), 0) INTO expected
                FROM public.ledger_entries WHERE account_id = target;
            IF actual IS DISTINCT FROM expected THEN
                RAISE EXCEPTION 'Balance must match journal' USING ERRCODE = '23514';
            END IF;
            RETURN NULL;
        END; $$;
        ALTER TABLE accounts DROP COLUMN ledger_balance;
        SET CONSTRAINTS ALL DEFERRED;
    """)
