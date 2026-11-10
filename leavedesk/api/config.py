"""Settings come from environment variables (or a .env file), never from code."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Every variable starts with LEAVEDESK_, e.g. LEAVEDESK_JWT_SECRET.
    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="LEAVEDESK_", extra="ignore"
    )

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
