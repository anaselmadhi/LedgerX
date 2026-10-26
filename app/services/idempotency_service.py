"""PostgreSQL reservations are part of the same transaction as the monetary effect."""

import hashlib
import json
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError
from app.db.models import SYSTEM_USER_ID, IdempotencyRecord


def reserve(
    session: Session,
    operation: str,
    key: str | None,
    payload: dict[str, Any],
    principal_id: UUID = SYSTEM_USER_ID,
) -> IdempotencyRecord | None:
    if key is None:
        return None
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    fingerprint = hashlib.sha256(canonical.encode()).hexdigest()
    # Concurrent INSERT waits for commit/rollback; the next statement gets a new
    # READ COMMITTED snapshot and sees the winner, or our own new reservation.
    created = session.scalar(
        insert(IdempotencyRecord)
        .values(principal_id=principal_id, operation=operation, key=key, fingerprint=fingerprint)
        .on_conflict_do_nothing(
            index_elements=[
                IdempotencyRecord.principal_id,
                IdempotencyRecord.operation,
                IdempotencyRecord.key,
            ]
        )
        .returning(IdempotencyRecord)
    )
    if created is not None:
        # Our INSERT owns the uncommitted row. Competing inserts wait on the
        # unique key until our transaction ends, so another SELECT/FOR UPDATE
        # cannot strengthen this reservation. RETURNING saves one DB round trip.
        return created
    record = session.scalar(
        select(IdempotencyRecord)
        .where(
            IdempotencyRecord.principal_id == principal_id,
            IdempotencyRecord.operation == operation,
            IdempotencyRecord.key == key,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    assert record is not None
    if record.fingerprint != fingerprint:
        raise DomainError(
            "Idempotency key already used for another payload", 409, "idempotency_conflict"
        )
    return record
