"""Compensating transfers, scoped idempotency and database boundary hardening."""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE accounts ADD CONSTRAINT account_balance_range
            CHECK (balance BETWEEN -9000000000000000000 AND 9000000000000000000);
        ALTER TABLE transfers ADD CONSTRAINT transfer_amount_limit
            CHECK (amount <= 9000000000000000000);
        ALTER TABLE transfers ADD COLUMN reversal_of UUID UNIQUE REFERENCES transfers(id);
        ALTER TABLE transfers ADD COLUMN reversal_reason VARCHAR(200);
        ALTER TABLE transfers ADD CONSTRAINT reversal_metadata CHECK (
            (reversal_of IS NULL AND reversal_reason IS NULL) OR
            (reversal_of IS NOT NULL AND reversal_reason IS NOT NULL
             AND length(btrim(reversal_reason)) BETWEEN 1 AND 200)
        );
        ALTER TABLE idempotency_records ADD COLUMN operation VARCHAR(16)
            NOT NULL DEFAULT 'transfer';
        ALTER TABLE idempotency_records ALTER COLUMN operation DROP DEFAULT;
        ALTER TABLE idempotency_records DROP CONSTRAINT idempotency_records_pkey;
        ALTER TABLE idempotency_records ADD PRIMARY KEY (operation, key);

        CREATE FUNCTION protect_account_identity() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'Accounts cannot be deleted' USING ERRCODE = '23514';
            END IF;
            IF ROW(NEW.id, NEW.currency, NEW.is_system, NEW.created_at)
                IS DISTINCT FROM ROW(OLD.id, OLD.currency, OLD.is_system, OLD.created_at) THEN
                RAISE EXCEPTION 'Account identity is immutable' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END; $$;
        CREATE TRIGGER immutable_account_identity BEFORE UPDATE OR DELETE ON accounts
            FOR EACH ROW EXECUTE FUNCTION protect_account_identity();

        CREATE FUNCTION validate_reversal() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE original transfers%ROWTYPE;
        BEGIN
            IF NEW.reversal_of IS NULL THEN RETURN NEW; END IF;
            SELECT * INTO original FROM transfers WHERE id = NEW.reversal_of;
            IF NOT FOUND OR original.reversal_of IS NOT NULL
                OR original.source_account_id = '00000000-0000-0000-0000-000000000001'::uuid
                OR original.destination_account_id = '00000000-0000-0000-0000-000000000001'::uuid
                OR NEW.source_account_id <> original.destination_account_id
                OR NEW.destination_account_id <> original.source_account_id
                OR NEW.amount <> original.amount OR NEW.currency <> original.currency THEN
                RAISE EXCEPTION 'Invalid compensating transfer' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END; $$;
        CREATE TRIGGER valid_reversal BEFORE INSERT ON transfers
            FOR EACH ROW EXECUTE FUNCTION validate_reversal();

        CREATE FUNCTION protect_idempotency_result() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' OR OLD.transaction_id IS NOT NULL
                OR ROW(OLD.operation, OLD.key, OLD.fingerprint)
                   IS DISTINCT FROM ROW(NEW.operation, NEW.key, NEW.fingerprint) THEN
                RAISE EXCEPTION 'Idempotency result is immutable' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END; $$;
        CREATE TRIGGER immutable_idempotency BEFORE UPDATE OR DELETE ON idempotency_records
            FOR EACH ROW EXECUTE FUNCTION protect_idempotency_result();

        CREATE FUNCTION check_completed_idempotency() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF EXISTS (SELECT 1 FROM idempotency_records
                WHERE operation = NEW.operation AND key = NEW.key AND transaction_id IS NULL) THEN
                RAISE EXCEPTION 'Idempotency reservation must complete' USING ERRCODE = '23514';
            END IF;
            RETURN NULL;
        END; $$;
        CREATE CONSTRAINT TRIGGER completed_idempotency AFTER INSERT ON idempotency_records
            DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
            EXECUTE FUNCTION check_completed_idempotency();
    """)


def downgrade():
    # Going back to a global key namespace is unsafe if operation scopes overlap.
    # Fail transactionally rather than deleting successful payment records.
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT key FROM idempotency_records GROUP BY key HAVING count(*) > 1)
            THEN RAISE EXCEPTION 'Scoped keys overlap; cannot downgrade without data loss';
            END IF;
            IF EXISTS (SELECT 1 FROM transfers WHERE reversal_of IS NOT NULL)
            THEN RAISE EXCEPTION 'Reversals exist; cannot discard their audit metadata';
            END IF;
        END; $$;
        DROP TRIGGER completed_idempotency ON idempotency_records;
        DROP TRIGGER immutable_idempotency ON idempotency_records;
        DROP FUNCTION check_completed_idempotency(), protect_idempotency_result();
        DROP TRIGGER valid_reversal ON transfers;
        DROP FUNCTION validate_reversal();
        DROP TRIGGER immutable_account_identity ON accounts;
        DROP FUNCTION protect_account_identity();
        ALTER TABLE idempotency_records DROP CONSTRAINT idempotency_records_pkey;
        ALTER TABLE idempotency_records DROP COLUMN operation;
        ALTER TABLE idempotency_records ADD PRIMARY KEY (key);
        ALTER TABLE transfers DROP CONSTRAINT reversal_metadata;
        ALTER TABLE transfers DROP COLUMN reversal_of, DROP COLUMN reversal_reason;
        ALTER TABLE transfers DROP CONSTRAINT transfer_amount_limit;
        ALTER TABLE accounts DROP CONSTRAINT account_balance_range;
    """)
