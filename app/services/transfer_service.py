from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError
from app.db.models import (
    MAX_AMOUNT,
    SYSTEM_ACCOUNT_ID,
    SYSTEM_USER_ID,
    Account,
    LedgerEntry,
    Transfer,
)
from app.schemas.transfer import TransferCreate
from app.services.idempotency_service import reserve


def get_transfer(session: Session, transaction_id: UUID, owner_id: UUID | None = None) -> Transfer:
    query = select(Transfer).where(Transfer.id == transaction_id)
    if owner_id is not None:
        owned = select(Account.id).where(Account.owner_id == owner_id)
        query = query.where(
            Transfer.source_account_id.in_(owned) | Transfer.destination_account_id.in_(owned)
        )
    transfer = session.scalar(query)
    if transfer is None:
        raise DomainError("Transfer not found", 404, "transfer_not_found")
    return transfer


def post_entries(session: Session, transfer: Transfer) -> None:
    """Kept separate so rollback tests can inject a failure after balance changes."""
    session.add_all(
        [
            LedgerEntry(
                transaction_id=transfer.id,
                account_id=account_id,
                amount=amount,
                currency=transfer.currency,
            )
            for account_id, amount in (
                (transfer.source_account_id, -transfer.amount),
                (transfer.destination_account_id, transfer.amount),
            )
        ]
    )
    session.flush()


def transfer_money(
    session: Session,
    request: TransferCreate,
    key: str | None = None,
    *,
    funding: bool = False,
    reversal_of: UUID | None = None,
    reversal_reason: str | None = None,
    actor_id: UUID | None = None,
) -> Transfer:
    """Caller owns the transaction. Any exception must roll back the entire call."""
    record = reserve(
        session,
        "funding" if funding else "transfer",
        key,
        request.model_dump(mode="json"),
        actor_id or SYSTEM_USER_ID,
    )
    if record is not None and record.transaction_id is not None:
        session.info["idempotency_replayed"] = True
        return get_transfer(session, record.transaction_id)

    ids = sorted([request.source_account_id, request.destination_account_id])
    accounts = session.scalars(
        select(Account)
        .where(Account.id.in_(ids))
        .order_by(Account.id)
        .with_for_update()
        # A Session may have loaded an account before another transaction committed.
        # Row locking alone does not refresh SQLAlchemy's identity map.
        .execution_options(populate_existing=True)
    ).all()
    by_id = {account.id: account for account in accounts}
    if len(by_id) != 2:
        raise DomainError("Account not found", 404, "account_not_found")
    source = by_id[request.source_account_id]
    destination = by_id[request.destination_account_id]
    if actor_id is not None and not funding and source.owner_id != actor_id:
        raise DomainError("Account not found", 404, "account_not_found")
    if destination.is_system or (source.is_system and not funding):
        raise DomainError(
            "System accounts are not available through this API", 404, "account_not_found"
        )
    if funding and source.id != SYSTEM_ACCOUNT_ID:
        raise DomainError("Invalid funding source")
    if source.currency != request.currency or destination.currency != request.currency:
        raise DomainError("Incompatible currencies")
    if not source.is_system and source.balance < request.amount:
        raise DomainError("Insufficient funds", 409, "insufficient_funds")
    if destination.balance + request.amount > MAX_AMOUNT:
        raise DomainError("Destination balance limit exceeded", 409, "balance_limit_exceeded")
    if source.balance - request.amount < -MAX_AMOUNT:
        raise DomainError("System funding limit exceeded", 409, "balance_limit_exceeded")

    transfer = Transfer(
        **request.model_dump(), reversal_of=reversal_of, reversal_reason=reversal_reason
    )
    session.add(transfer)
    session.flush()
    source.balance -= request.amount
    destination.balance += request.amount
    post_entries(session, transfer)
    if record is not None:
        record.transaction_id = transfer.id
    session.flush()
    return transfer


def reverse_transfer(
    session: Session,
    transaction_id: UUID,
    reason: str,
    key: str | None = None,
    actor_id: UUID | None = None,
) -> Transfer:
    """Full compensation, once per original transfer, with funds checked normally."""
    record = reserve(
        session,
        "reversal",
        key,
        {"transfer_id": str(transaction_id), "reason": reason},
        actor_id or SYSTEM_USER_ID,
    )
    if record is not None and record.transaction_id is not None:
        session.info["idempotency_replayed"] = True
        return get_transfer(session, record.transaction_id)
    # NO KEY UPDATE serializes reversals without conflicting with FK KEY SHARE locks.
    original = session.scalar(
        select(Transfer).where(Transfer.id == transaction_id).with_for_update(key_share=True)
    )
    if original is None:
        raise DomainError("Transfer not found", 404, "transfer_not_found")
    if actor_id is not None:
        recipient_owner = session.scalar(
            select(Account.owner_id).where(Account.id == original.destination_account_id)
        )
        if recipient_owner != actor_id:
            raise DomainError("Transfer not found", 404, "transfer_not_found")
    if original.reversal_of is not None or SYSTEM_ACCOUNT_ID in (
        original.source_account_id,
        original.destination_account_id,
    ):
        raise DomainError("This transfer cannot be reversed", 409, "reversal_not_allowed")
    existing = session.scalar(select(Transfer).where(Transfer.reversal_of == original.id))
    if existing is not None:
        raise DomainError("Transfer already reversed", 409, "already_reversed")
    result = transfer_money(
        session,
        TransferCreate(
            source_account_id=original.destination_account_id,
            destination_account_id=original.source_account_id,
            amount=original.amount,
            currency=original.currency,
        ),
        reversal_of=original.id,
        reversal_reason=reason,
        actor_id=actor_id,
    )
    if record is not None:
        record.transaction_id = result.id
    session.flush()
    return result
