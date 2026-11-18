"""Capstone 3: what PostgreSQL adds. These tests talk to the database directly."""

from __future__ import annotations

import asyncio
import threading
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from leavedesk.api.config import Settings
from leavedesk.api.main import create_app
from leavedesk.domain.exceptions import InvalidTransitionError
from leavedesk.domain.models import LeaveRequest, LeaveType
from leavedesk.worker import drain_outbox
from tests.conftest import TODAY, leave


def sql(app: FastAPI, query: str, **params: Any) -> list[Any]:
    """Run raw SQL (always with bound :params, never string formatting)."""
    with app.state.container.engine.begin() as conn:
        result = conn.execute(text(query), params)
        return list(result) if result.returns_rows else []


def test_data_survives_a_restart(settings: Settings, priya: TestClient) -> None:
    created = priya.post("/leave-requests", json=leave()).json()

    restarted = create_app(settings, today=lambda: TODAY)  # a brand-new app
    found = restarted.state.container.repo.get_request(created["id"])
    assert found.reason == "Family trip"
    restarted.state.container.engine.dispose()


def test_database_refuses_overlap_even_without_the_app(
    app: FastAPI, people: dict[str, Any]
) -> None:
    insert = """INSERT INTO leave_requests
        (id, employee_id, leave_type, start_date, end_date, reason, status, created_at)
        VALUES (gen_random_uuid(), :emp, 'ANNUAL', :start, :end, 'Direct SQL', 'PENDING', now())"""
    sql(app, insert, emp=people["priya"], start="2026-11-16", end="2026-11-20")
    with pytest.raises(IntegrityError, match="ex_request_no_overlap"):
        sql(app, insert, emp=people["priya"], start="2026-11-18", end="2026-11-19")


def test_database_refuses_end_before_start(
    app: FastAPI, people: dict[str, Any]
) -> None:
    with pytest.raises(IntegrityError, match="ck_request_dates"):
        sql(
            app,
            """INSERT INTO leave_requests
            (id, employee_id, leave_type, start_date, end_date, reason, status, created_at)
            VALUES (gen_random_uuid(), :emp, 'ANNUAL', '2026-11-20', '2026-11-16',
                    'Backwards', 'PENDING', now())""",
            emp=people["priya"],
        )


def test_parallel_approvals_only_one_deducts(
    app: FastAPI, people: dict[str, Any]
) -> None:
    service = app.state.container.service
    request = asyncio.run(
        service.apply(
            LeaveRequest(
                employee_id=people["priya"],
                leave_type=LeaveType.ANNUAL,
                start=TODAY.replace(day=16),
                end=TODAY.replace(day=20),
                reason="Family trip",
            )
        )
    )
    start_together = threading.Barrier(2)
    results: list[str] = []

    def approve() -> None:
        start_together.wait()  # both threads go at the same moment
        try:
            asyncio.run(service.approve(request.id, manager_id=people["arjun"]))
            results.append("approved")
        except InvalidTransitionError:
            results.append("409")

    threads = [threading.Thread(target=approve) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sorted(results) == ["409", "approved"]
    balance = app.state.container.repo.get_balance(people["priya"], LeaveType.ANNUAL)
    assert balance.used == 5  # deducted once, not twice
    deductions = sql(
        app, "SELECT count(*) FROM leave_ledger WHERE request_id = :id", id=request.id
    )
    assert deductions[0][0] == 1


def test_ledger_adds_up_to_the_balance(
    priya: TestClient, arjun: TestClient, people: dict[str, Any], app: FastAPI
) -> None:
    created = priya.post("/leave-requests", json=leave()).json()
    arjun.post(f"/leave-requests/{created['id']}/approve")

    total = sql(
        app,
        """SELECT sum(days) FROM leave_ledger
           WHERE employee_id = :emp AND leave_type = 'ANNUAL'""",
        emp=people["priya"],
    )[0][0]
    remaining = app.state.container.repo.get_balance(
        people["priya"], LeaveType.ANNUAL
    ).remaining
    assert float(total) == remaining == 13  # 18 granted - 5 used


def test_failed_approval_leaves_no_outbox_message(
    priya: TestClient,
    arjun: TestClient,
    app: FastAPI,
    people: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = priya.post("/leave-requests", json=leave()).json()
    repo = app.state.container.repo
    original = repo.add_outbox

    def outbox_then_crash(*args: Any) -> None:
        original(*args)  # the message IS written...
        raise RuntimeError("crash before commit")  # ...then something breaks

    monkeypatch.setattr(repo, "add_outbox", outbox_then_crash)
    with pytest.raises(RuntimeError):
        asyncio.run(app.state.container.service.approve(created["id"], people["arjun"]))

    # Rolled back as one unit: no message, no deduction, still PENDING.
    approved_msgs = sql(
        app, "SELECT count(*) FROM notification_outbox WHERE event = 'approved'"
    )
    assert approved_msgs[0][0] == 0
    assert repo.get_balance(people["priya"], LeaveType.ANNUAL).used == 0
    assert repo.get_request(created["id"]).status == "PENDING"


def test_worker_sends_each_outbox_message_once(priya: TestClient, app: FastAPI) -> None:
    priya.post("/leave-requests", json=leave())
    container = app.state.container
    email = AsyncMock()
    container.notifications.notifiers = [email]
    session_factory = container.repo.session_factory

    assert asyncio.run(drain_outbox(session_factory, container.notifications)) == 1
    assert asyncio.run(drain_outbox(session_factory, container.notifications)) == 0
    email.send.assert_awaited_once()  # the manager's "submitted" email
