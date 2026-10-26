from fastapi import APIRouter, Depends, Response

from app.api.dependencies import DB, CurrentUser
from app.core.auth_limits import auth_attempt
from app.core.config import settings
from app.schemas.auth import Credentials, SessionRead, TokenRead, UserRead
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.get("/me", response_model=SessionRead)
def me(principal: CurrentUser, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return SessionRead(
        id=principal.id,
        username=principal.username,
        is_admin=principal.is_admin,
        dev_funding_enabled=principal.is_admin and settings.enable_dev_funding,
    )


@router.post(
    "/register", response_model=UserRead, status_code=201, dependencies=[Depends(auth_attempt)]
)
def register(body: Credentials, session: DB):
    with session.begin():
        return auth_service.register(session, body)


@router.post("/login", response_model=TokenRead, dependencies=[Depends(auth_attempt)])
def login(body: Credentials, session: DB, response: Response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    with session.begin():
        return auth_service.login(session, body)


@router.post("/logout", status_code=204)
def logout(session: DB, principal: CurrentUser):
    with session.begin():
        auth_service.logout(session, principal)
    return Response(status_code=204)
