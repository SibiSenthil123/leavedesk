"""One engine (a pool of connections) per app, and a factory for sessions."""

from __future__ import annotations

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from leavedesk.api.config import DatabaseSettings


def make_engine(settings: DatabaseSettings, echo: bool = False) -> Engine:
    # options= sets the timeouts on every connection, so no query can hang forever.
    options = (
        f"-c statement_timeout={settings.statement_timeout_ms} "
        f"-c lock_timeout={settings.lock_timeout_ms}"
    )
    return create_engine(
        settings.database_url,
        echo=echo,  # True prints every SQL statement: handy for spotting N+1 queries
        pool_pre_ping=True,  # checks a pooled connection is alive before using it
        connect_args={"options": options},
    )


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    # expire_on_commit=False: objects stay readable after the transaction ends.
    return sessionmaker(engine, expire_on_commit=False)
