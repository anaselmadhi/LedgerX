from fastapi import APIRouter

from app.api.dependencies import DB, AdminUser
from app.schemas.operations import ReconciliationRead
from app.services.reconciliation_service import reconcile

router = APIRouter(prefix="/operations", tags=["operations"])


@router.get("/reconciliation", response_model=ReconciliationRead)
def reconciliation(session: DB, principal: AdminUser):
    """Full ledger audit in a single consistent database snapshot; O(accounts + entries)."""
    return reconcile(session)
