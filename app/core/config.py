from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

APP_VERSION = "0.3.0"
SCHEMA_REVISION = "0004"


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://ledgerx:ledgerx_local@localhost:5432/ledgerx"
    enable_dev_funding: bool = False
    public_demo: bool = False
    token_lifetime_seconds: int = Field(default=3600, ge=300, le=86400)
    auth_attempts_per_peer: int = Field(default=10, ge=1, le=10000)
    auth_attempts_total: int = Field(default=120, ge=1, le=100000)
    auth_window_seconds: int = Field(default=60, ge=1, le=3600)
    auth_max_concurrent: int = Field(default=2, ge=1, le=16)
    db_pool_size: int = Field(default=10, ge=1, le=100)
    db_max_overflow: int = Field(default=10, ge=0, le=100)
    db_pool_timeout_seconds: float = Field(default=5, gt=0, le=60)
    db_connect_timeout_seconds: int = Field(default=5, ge=1, le=60)
    db_lock_timeout_ms: int = Field(default=2000, ge=1, le=60000)
    db_statement_timeout_ms: int = Field(default=10000, ge=1, le=120000)
    db_idle_transaction_timeout_ms: int = Field(default=15000, ge=1, le=120000)
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    @field_validator("database_url")
    @classmethod
    def use_psycopg3(cls, value: str) -> str:
        # Hosted providers commonly supply postgresql://, which otherwise selects psycopg2.
        try:
            url = make_url(value)
        except ArgumentError:
            raise ValueError("DATABASE_URL must be a valid PostgreSQL URL") from None
        if url.drivername in {"postgres", "postgresql"}:
            return url.set(drivername="postgresql+psycopg").render_as_string(hide_password=False)
        if url.drivername != "postgresql+psycopg":
            raise ValueError("LedgerX requires PostgreSQL with the psycopg driver")
        return value


settings = Settings()
