import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

SYSTEM_ACCOUNT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
SYSTEM_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
LEGACY_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
MAX_AMOUNT = 9_000_000_000_000_000_000


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuthToken(Base):
    __tablename__ = "auth_tokens"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        CheckConstraint("currency = 'EUR'", name="account_currency"),
        CheckConstraint("is_system OR balance >= 0", name="nonnegative_customer_balance"),
        CheckConstraint(
            f"balance BETWEEN {-MAX_AMOUNT} AND {MAX_AMOUNT}", name="account_balance_range"
        ),
        CheckConstraint(
            "NOT is_system OR id = '00000000-0000-0000-0000-000000000001'::uuid",
            name="only_dedicated_system_account",
        ),
        CheckConstraint(
            "(is_system AND owner_id IS NULL) OR (NOT is_system AND owner_id IS NOT NULL)",
            name="account_ownership",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    balance: Mapped[int] = mapped_column(BigInteger, default=0)
    # Private, database-maintained exact integer projection. Deferred so ordinary
    # account reads do not fetch a second balance; only SQL triggers write it.
    ledger_balance: Mapped[Decimal] = mapped_column(
        Numeric, server_default=text("0"), deferred=True
    )
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Transfer(Base):
    __tablename__ = "transfers"
    __table_args__ = (
        CheckConstraint("amount > 0", name="positive_transfer"),
        CheckConstraint("source_account_id <> destination_account_id", name="distinct_accounts"),
        CheckConstraint("currency = 'EUR'", name="transfer_currency"),
        CheckConstraint(f"amount <= {MAX_AMOUNT}", name="transfer_amount_limit"),
        CheckConstraint(
            "(reversal_of IS NULL AND reversal_reason IS NULL) OR "
            "(reversal_of IS NOT NULL AND reversal_reason IS NOT NULL "
            "AND length(btrim(reversal_reason)) BETWEEN 1 AND 200)",
            name="reversal_metadata",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"))
    destination_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"))
    amount: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3))
    reversal_of: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("transfers.id"), unique=True)
    reversal_reason: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    __table_args__ = (
        UniqueConstraint("transaction_id", "account_id"),
        CheckConstraint("amount <> 0", name="nonzero_entry"),
        CheckConstraint("currency = 'EUR'", name="entry_currency"),
        Index("ix_entries_account_created_id", "account_id", "created_at", "id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    transaction_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("transfers.id"))
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"))
    amount: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    principal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), primary_key=True, default=SYSTEM_USER_ID
    )
    operation: Mapped[str] = mapped_column(String(16), primary_key=True, default="transfer")
    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64))
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("transfers.id"))
