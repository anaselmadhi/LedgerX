"""Users, revocable tokens, immutable account ownership and customer-scoped keys."""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE users (
            id UUID PRIMARY KEY,
            username VARCHAR(64) NOT NULL UNIQUE,
            password_hash VARCHAR(256) NOT NULL,
            is_admin BOOLEAN NOT NULL,
            is_active BOOLEAN NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        INSERT INTO users (id, username, password_hash, is_admin, is_active) VALUES
            ('00000000-0000-0000-0000-000000000001', '_system', 'disabled', false, false),
            ('00000000-0000-0000-0000-000000000002', '_legacy', 'disabled', false, false);
        CREATE TABLE auth_tokens (
            token_hash VARCHAR(64) PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id),
            expires_at TIMESTAMPTZ NOT NULL,
            revoked_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_auth_tokens_user_id ON auth_tokens(user_id);
        CREATE INDEX ix_auth_tokens_expires_at ON auth_tokens(expires_at);
        ALTER TABLE accounts ADD COLUMN owner_id UUID REFERENCES users(id);
        UPDATE accounts SET owner_id = '00000000-0000-0000-0000-000000000002'
            WHERE NOT is_system;
        SET CONSTRAINTS ALL IMMEDIATE;
        SET CONSTRAINTS ALL DEFERRED;
        ALTER TABLE accounts ADD CONSTRAINT account_ownership CHECK (
            (is_system AND owner_id IS NULL) OR (NOT is_system AND owner_id IS NOT NULL)
        );
        CREATE INDEX ix_accounts_owner_id ON accounts(owner_id);
        ALTER TABLE idempotency_records ADD COLUMN principal_id UUID NOT NULL
            DEFAULT '00000000-0000-0000-0000-000000000002' REFERENCES users(id);
        ALTER TABLE idempotency_records ALTER COLUMN principal_id DROP DEFAULT;
        ALTER TABLE idempotency_records DROP CONSTRAINT idempotency_records_pkey;
        ALTER TABLE idempotency_records ADD PRIMARY KEY (principal_id, operation, key);

        CREATE OR REPLACE FUNCTION protect_account_identity() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'Accounts cannot be deleted' USING ERRCODE = '23514';
            END IF;
            IF ROW(NEW.id, NEW.currency, NEW.is_system, NEW.created_at, NEW.owner_id)
                IS DISTINCT FROM ROW(
                    OLD.id, OLD.currency, OLD.is_system, OLD.created_at, OLD.owner_id)
            THEN RAISE EXCEPTION 'Account identity is immutable' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END; $$;
        CREATE OR REPLACE FUNCTION protect_idempotency_result()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' OR OLD.transaction_id IS NOT NULL
                OR ROW(OLD.principal_id, OLD.operation, OLD.key, OLD.fingerprint)
                   IS DISTINCT FROM ROW(NEW.principal_id, NEW.operation, NEW.key, NEW.fingerprint)
            THEN RAISE EXCEPTION 'Idempotency result is immutable' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END; $$;
        CREATE OR REPLACE FUNCTION check_completed_idempotency()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF EXISTS (SELECT 1 FROM idempotency_records
                WHERE principal_id = NEW.principal_id AND operation = NEW.operation
                AND key = NEW.key AND transaction_id IS NULL)
            THEN RAISE EXCEPTION 'Idempotency reservation must complete' USING ERRCODE = '23514';
            END IF;
            RETURN NULL;
        END; $$;
    """)


def downgrade():
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM users WHERE id NOT IN (
                '00000000-0000-0000-0000-000000000001'::uuid,
                '00000000-0000-0000-0000-000000000002'::uuid))
                OR EXISTS (SELECT 1 FROM auth_tokens)
                OR EXISTS (SELECT operation, key FROM idempotency_records
                           GROUP BY operation, key HAVING count(*) > 1)
            THEN RAISE EXCEPTION 'Authentication data exists; refusing lossy downgrade';
            END IF;
        END; $$;
        CREATE OR REPLACE FUNCTION protect_account_identity() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'Accounts cannot be deleted' USING ERRCODE = '23514';
            END IF;
            IF ROW(NEW.id, NEW.currency, NEW.is_system, NEW.created_at)
                IS DISTINCT FROM ROW(OLD.id, OLD.currency, OLD.is_system, OLD.created_at)
            THEN RAISE EXCEPTION 'Account identity is immutable' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END; $$;
        CREATE OR REPLACE FUNCTION protect_idempotency_result()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' OR OLD.transaction_id IS NOT NULL
                OR ROW(OLD.operation, OLD.key, OLD.fingerprint)
                   IS DISTINCT FROM ROW(NEW.operation, NEW.key, NEW.fingerprint)
            THEN RAISE EXCEPTION 'Idempotency result is immutable' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END; $$;
        CREATE OR REPLACE FUNCTION check_completed_idempotency()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF EXISTS (SELECT 1 FROM idempotency_records WHERE operation = NEW.operation
                       AND key = NEW.key AND transaction_id IS NULL)
            THEN RAISE EXCEPTION 'Idempotency reservation must complete' USING ERRCODE = '23514';
            END IF;
            RETURN NULL;
        END; $$;
        ALTER TABLE accounts DROP CONSTRAINT account_ownership;
        ALTER TABLE accounts DROP COLUMN owner_id;
        ALTER TABLE idempotency_records DROP CONSTRAINT idempotency_records_pkey;
        ALTER TABLE idempotency_records DROP COLUMN principal_id;
        ALTER TABLE idempotency_records ADD PRIMARY KEY (operation, key);
        DROP TABLE auth_tokens, users;
    """)
