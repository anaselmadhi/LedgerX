from uuid import UUID

from fastapi import APIRouter, Response

from app.api.dependencies import DB, AdminUser, CurrentUser, IdempotencyKey
from app.core.config import settings
from app.core.exceptions import DomainError
from app.db.models import SYSTEM_ACCOUNT_ID
from app.schemas.transfer import FundingCreate, ReversalCreate, TransferCreate, TransferRead
from app.services.transfer_service import get_transfer, reverse_transfer, transfer_money

router = APIRouter(tags=["transfers"])


@router.post("/transfers", response_model=TransferRead, status_code=201)
def create_transfer(
    body: TransferCreate,
    session: DB,
    principal: CurrentUser,
    response: Response,
    idempotency_key: IdempotencyKey = None,
):
    with session.begin():
        result = transfer_money(session, body, idempotency_key, actor_id=principal.id)
    response.headers["Idempotency-Replayed"] = str(
        session.info.get("idempotency_replayed", False)
    ).lower()
    return result


@router.get("/transfers/{transaction_id}", response_model=TransferRead)
def retrieve_transfer(transaction_id: UUID, session: DB, principal: CurrentUser):
    return get_transfer(session, transaction_id, principal.id)


@router.post("/dev/funding", response_model=TransferRead, status_code=201)
def fund(
    body: FundingCreate,
    session: DB,
    principal: AdminUser,
    response: Response,
    idempotency_key: IdempotencyKey = None,
):
    if not settings.enable_dev_funding:
        raise DomainError("Not found", 404)
    if body.destination_account_id == SYSTEM_ACCOUNT_ID:
        raise DomainError("Account not found", 404, "account_not_found")
    request = TransferCreate(source_account_id=SYSTEM_ACCOUNT_ID, **body.model_dump())
    with session.begin():
        result = transfer_money(
            session, request, idempotency_key, funding=True, actor_id=principal.id
        )
    response.headers["Idempotency-Replayed"] = str(
        session.info.get("idempotency_replayed", False)
    ).lower()
    return result


@router.post("/transfers/{transaction_id}/reversal", response_model=TransferRead, status_code=201)
def reverse(
    transaction_id: UUID,
    body: ReversalCreate,
    session: DB,
    principal: CurrentUser,
    response: Response,
    idempotency_key: IdempotencyKey = None,
):
    with session.begin():
        result = reverse_transfer(
            session, transaction_id, body.reason, idempotency_key, principal.id
        )
    response.headers["Idempotency-Replayed"] = str(
        session.info.get("idempotency_replayed", False)
    ).lower()
    return result
