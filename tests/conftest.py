"""Shared fixtures: a fresh app per test, logged-in clients and a mocked notifier.

Capstone 3: the app now stores everything in PostgreSQL. The tests use a separate
database (leavedesk_test), build its tables once with Alembic, and empty them before
every test so each test starts clean."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from datetime import date
from typing import Any
from unittest.mock import AsyncMock

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, text

from leavedesk.api.config import Settings
from leavedesk.api.deps import get_notifications
from leavedesk.api.main import create_app

PASSWORD = "test-password-123"
TODAY = date(2026, 11, 9)  # a Monday, so the dates in the tests are easy to read
TEST_DATABASE_URL = os.environ.get(
    "LEAVEDESK_TEST_DATABASE_URL",
    "postgresql+psycopg://leavedesk:leavedesk-dev-only@localhost:5433/leavedesk_test",
)
TABLES = "notification_outbox, leave_ledger, leave_requests, leave_balances, employees"


@pytest.fixture(scope="session")
def migrated_database() -> str:
    """Run every Alembic migration once, so the tests also prove the migrations work."""
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    command.upgrade(config, "head")
    return TEST_DATABASE_URL


@pytest.fixture
def clean_database(migrated_database: str) -> str:
    """Empty every table before the test."""
    engine = create_engine(migrated_database)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))
    engine.dispose()
    return migrated_database


@pytest.fixture
def settings(clean_database: str) -> Settings:
    return Settings(
        jwt_secret=SecretStr("test-secret-that-is-at-least-32-characters"),
        demo_password=SecretStr(PASSWORD),
        email_delay_seconds=0,
        database_url=clean_database,
        _env_file=None,  # type: ignore[call-arg]  # ignore any local .env
    )


@pytest.fixture
def app(settings: Settings) -> Iterator[FastAPI]:
    app = create_app(settings, today=lambda: TODAY)
    yield app
    app.state.container.engine.dispose()  # close this test's database connections


@pytest.fixture
def notifier(app: FastAPI) -> AsyncMock:
    """Replaces the real NotificationService so tests can check what was queued."""
    mock = AsyncMock()
    app.dependency_overrides[get_notifications] = lambda: mock
    return mock


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest.fixture
def people(app: FastAPI) -> dict[str, Any]:
    """id of each seeded person, by first name."""
    return {
        e.name.split()[0].lower(): e.id
        for e in app.state.container.repo.all_employees()
    }


@pytest.fixture
def login(app: FastAPI) -> Callable[[str], TestClient]:
    """login("priya") gives a client that sends Priya's token on every request."""
    clients: list[TestClient] = []

    def _login(name: str) -> TestClient:
        c = TestClient(app)
        r = c.post(
            "/auth/login",
            data={"username": f"{name}@leavedesk.dev", "password": PASSWORD},
        )
        assert r.status_code == 200, r.text
        c.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
        clients.append(c)
        return c

    return _login


@pytest.fixture
def priya(login: Callable[[str], TestClient]) -> TestClient:
    return login("priya")


@pytest.fixture
def arjun(login: Callable[[str], TestClient]) -> TestClient:
    """Priya's manager."""
    return login("arjun")


@pytest.fixture
def kiran(login: Callable[[str], TestClient]) -> TestClient:
    """Priya's colleague: same manager, no rights over her requests."""
    return login("kiran")


def leave(**overrides: Any) -> dict[str, Any]:
    """A valid annual-leave body: Mon 16 to Fri 20 Nov 2026 (5 working days)."""
    body: dict[str, Any] = {
        "leave_type": "ANNUAL",
        "start": "2026-11-16",
        "end": "2026-11-20",
        "reason": "Family trip",
    }
    body.update(overrides)
    return body
