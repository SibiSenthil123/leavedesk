"""Shared fixtures: a fresh app per test, logged-in clients and a mocked notifier."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import date
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from leavedesk.api.config import Settings
from leavedesk.api.deps import get_notifications
from leavedesk.api.main import create_app

PASSWORD = "test-password-123"
TODAY = date(2026, 11, 9)  # a Monday, so the dates in the tests are easy to read


@pytest.fixture
def settings() -> Settings:
    return Settings(
        jwt_secret=SecretStr("test-secret-that-is-at-least-32-characters"),
        demo_password=SecretStr(PASSWORD),
        email_delay_seconds=0,
        _env_file=None,  # type: ignore[call-arg]  # ignore any local .env
    )


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings, today=lambda: TODAY)


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
