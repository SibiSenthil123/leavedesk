"""Alembic's start-up script: finds the database and runs the migrations."""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from leavedesk.api.config import DatabaseSettings
from leavedesk.db.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata  # lets `alembic revision --autogenerate` compare


def database_url() -> str:
    # Tests pass their own URL; everyone else uses the settings (.env).
    return config.get_main_option("sqlalchemy.url") or DatabaseSettings().database_url


def run_migrations_online() -> None:
    engine = create_engine(database_url())
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


run_migrations_online()
