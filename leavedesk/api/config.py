"""Settings come from environment variables (or a .env file), never from code."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Only the database address. Alembic and the outbox worker need this and nothing else."""

    # Every variable starts with LEAVEDESK_, e.g. LEAVEDESK_DATABASE_URL.
    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="LEAVEDESK_", extra="ignore"
    )

    database_url: str = (
        "postgresql+psycopg://leavedesk:leavedesk-dev-only@localhost:5433/leavedesk"
    )
    # A query or a lock wait longer than this is cancelled instead of hanging forever.
    statement_timeout_ms: int = Field(default=5000, ge=100)
    lock_timeout_ms: int = Field(default=3000, ge=100)


class Settings(DatabaseSettings):
    app_name: str = "LeaveDesk API"
    # No default on purpose: the app refuses to start without a real secret.
    jwt_secret: SecretStr = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = Field(default=30, ge=1, le=24 * 60)
    seed_demo_data: bool = True
    demo_password: SecretStr | None = None
    email_delay_seconds: float = Field(default=0.2, ge=0)
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Read the environment once and reuse the result."""
    return Settings()  # type: ignore[call-arg]  # values come from the environment
