"""Initial ledger with deferred consistency checks and immutable journal."""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE accounts (
            id UUID PRIMARY KEY,
            currency VARCHAR(3) NOT NULL CONSTRAINT account_currency CHECK (currency = 'EUR'),
            balance BIGINT NOT NULL,
            is_system BOOLEAN NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT nonnegative_customer_balance CHECK (is_system OR balance >= 0),
            CONSTRAINT only_dedicated_system_account CHECK (
                NOT is_system OR id = '00000000-0000-0000-0000-000000000001'::uuid
            )
        );
        CREATE TABLE transfers (
            id UUID PRIMARY KEY,
            source_account_id UUID NOT NULL REFERENCES accounts(id),
            destination_account_id UUID NOT NULL REFERENCES accounts(id),
            amount BIGINT NOT NULL CONSTRAINT positive_transfer CHECK (amount > 0),
            currency VARCHAR(3) NOT NULL CONSTRAINT transfer_currency CHECK (currency = 'EUR'),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT distinct_accounts CHECK (source_account_id <> destination_account_id)
        );
        CREATE TABLE ledger_entries (
            id UUID PRIMARY KEY,
            transaction_id UUID NOT NULL REFERENCES transfers(id),
            account_id UUID NOT NULL REFERENCES accounts(id),
            amount BIGINT NOT NULL CONSTRAINT nonzero_entry CHECK (amount <> 0),
            currency VARCHAR(3) NOT NULL CONSTRAINT entry_currency CHECK (currency = 'EUR'),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (transaction_id, account_id)
        );
        CREATE INDEX ix_entries_account_created_id ON ledger_entries(account_id, created_at, id);
        CREATE TABLE idempotency_records (
            key VARCHAR(128) PRIMARY KEY,
            fingerprint VARCHAR(64) NOT NULL,
            transaction_id UUID REFERENCES transfers(id)
        );
        INSERT INTO accounts (id, currency, balance, is_system)
        VALUES ('00000000-0000-0000-0000-000000000001', 'EUR', 0, true);

        CREATE FUNCTION reject_journal_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Journal rows are immutable' USING ERRCODE = '23514';
        END; $$;
        CREATE TRIGGER immutable_entries BEFORE UPDATE OR DELETE ON ledger_entries
            FOR EACH ROW EXECUTE FUNCTION reject_journal_mutation();
        CREATE TRIGGER immutable_transfers BEFORE UPDATE OR DELETE ON transfers
            FOR EACH ROW EXECUTE FUNCTION reject_journal_mutation();

        CREATE FUNCTION check_transfer_entries() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE target UUID; t transfers%ROWTYPE; n INTEGER; valid INTEGER;
        BEGIN
            IF TG_TABLE_NAME = 'transfers' THEN target := NEW.id;
            ELSE target := NEW.transaction_id; END IF;
            SELECT * INTO t FROM transfers WHERE id = target;
            SELECT count(*), count(*) FILTER (WHERE currency = t.currency AND (
                (account_id = t.source_account_id AND amount = -t.amount) OR
                (account_id = t.destination_account_id AND amount = t.amount)
            )) INTO n, valid FROM ledger_entries WHERE transaction_id = target;
            IF n <> 2 OR valid <> 2 THEN
                RAISE EXCEPTION 'Transfer requires matching debit and credit'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NULL;
        END; $$;
        CREATE CONSTRAINT TRIGGER balanced_transfer AFTER INSERT ON transfers
            DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION check_transfer_entries();
        CREATE CONSTRAINT TRIGGER balanced_entry AFTER INSERT ON ledger_entries
            DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION check_transfer_entries();

        CREATE FUNCTION check_account_balance() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE target UUID; actual BIGINT; expected NUMERIC;
        BEGIN
            IF TG_TABLE_NAME = 'accounts' THEN target := NEW.id;
            ELSE target := NEW.account_id; END IF;
            SELECT balance INTO actual FROM accounts WHERE id = target;
            SELECT coalesce(sum(amount), 0) INTO expected
                FROM ledger_entries WHERE account_id = target;
            IF actual IS DISTINCT FROM expected THEN
                RAISE EXCEPTION 'Balance must match journal' USING ERRCODE = '23514';
            END IF;
            RETURN NULL;
        END; $$;
        CREATE CONSTRAINT TRIGGER account_matches_ledger AFTER INSERT OR UPDATE ON accounts
            DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION check_account_balance();
        CREATE CONSTRAINT TRIGGER entry_matches_balance AFTER INSERT ON ledger_entries
            DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION check_account_balance();
    """)


def downgrade():
    op.execute("""
        DROP TABLE idempotency_records, ledger_entries, transfers, accounts;
        DROP FUNCTION check_account_balance(), check_transfer_entries(), reject_journal_mutation();
    """)
