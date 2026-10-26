import json
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.exc import TimeoutError as PoolTimeout

from app.api import accounts, auth, operations, transfers, web
from app.api.dependencies import DB, AdminUser
from app.core.config import APP_VERSION, SCHEMA_REVISION
from app.core.exceptions import DomainError
from app.core.observability import ObservabilityMiddleware

logger = logging.getLogger("ledgerx.errors")
# Default command-line runs emit structured request summaries. Existing host
# logging configurations (including test capture) keep their handlers.
logging.basicConfig(format="%(message)s")
logging.getLogger("ledgerx").setLevel(logging.INFO)

app = FastAPI(
    title="LedgerX",
    description="Authenticated local ledger demo. Integer EUR cents; no real money.",
    version=APP_VERSION,
)
app.add_middleware(ObservabilityMiddleware)
app.include_router(accounts.router)
app.include_router(auth.router)
app.include_router(transfers.router)
app.include_router(operations.router)
app.include_router(web.router)
# Build output is packaged under app/web. check_dir=False allows API-only installs.
app.mount("/assets", StaticFiles(directory=web.DIST / "assets", check_dir=False), name="assets")


@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.message,
            "code": exc.code,
            "request_id": getattr(request.state, "request_id", None),
        },
        headers={"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None,
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    # Never echo rejected password/token input in a validation error.
    errors = [{key: error[key] for key in ("loc", "msg", "type")} for error in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": errors})


@app.exception_handler(DBAPIError)
@app.exception_handler(PoolTimeout)
async def database_error_handler(request: Request, exc: SQLAlchemyError):
    sqlstate = getattr(getattr(exc, "orig", None), "sqlstate", None)
    transient = (
        isinstance(exc, PoolTimeout)
        or sqlstate in {"40001", "40P01", "55P03", "57014", "57P01", "57P02", "57P03"}
        or (sqlstate is not None and sqlstate.startswith("08"))
        or (isinstance(exc, DBAPIError) and (exc.connection_invalidated or sqlstate is None))
    )
    code = "database_temporarily_unavailable" if transient else "database_integrity_error"
    # DB exceptions can contain SQL parameters. Deliberately log only safe metadata.
    logger.error(
        json.dumps(
            {
                "event": "database_error",
                "code": code,
                "sqlstate": sqlstate,
                "request_id": getattr(request.state, "request_id", None),
                "correlation_id": getattr(request.state, "correlation_id", None),
            }
        )
    )
    return JSONResponse(
        status_code=503 if transient else 500,
        content={
            "detail": "Database temporarily unavailable" if transient else "Internal server error",
            "code": code,
            "request_id": getattr(request.state, "request_id", None),
        },
        headers={"Retry-After": "1"} if transient else None,
    )


@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, exc: Exception):
    logger.error(
        json.dumps(
            {
                "event": "unexpected_error",
                "type": type(exc).__name__,
                "request_id": getattr(request.state, "request_id", None),
                "correlation_id": getattr(request.state, "correlation_id", None),
            }
        )
    )
    return JSONResponse(
        status_code=500,
        headers={
            "X-Request-ID": getattr(request.state, "request_id", ""),
            "X-Correlation-ID": getattr(request.state, "correlation_id", ""),
        },
        content={
            "detail": "Internal server error",
            "code": "internal_error",
            "request_id": getattr(request.state, "request_id", None),
        },
    )


@app.get("/health")
def health(session: DB):
    try:
        revision = session.scalar(text("SELECT version_num FROM alembic_version"))
        if revision != SCHEMA_REVISION:
            return JSONResponse(status_code=503, content={"status": "schema_mismatch"})
        database_version = session.scalar(text("SHOW server_version"))
    except SQLAlchemyError:
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    return {
        "status": "ok",
        "version": APP_VERSION,
        "schema": revision,
        "postgresql": database_version,
    }


@app.get("/health/live", tags=["operations"])
def liveness():
    return {"status": "ok"}


@app.get("/metrics", include_in_schema=False)
def metrics(principal: AdminUser):
    return Response(generate_latest(), headers={"Content-Type": CONTENT_TYPE_LATEST})
