"""These tests use the REAL notifier (no mock), so background tasks really fill the inbox."""

import asyncio
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from leavedesk.domain.models import Notification, NotificationEvent
from tests.conftest import leave


def test_manager_gets_notified_when_employee_applies(
    priya: TestClient, arjun: TestClient
) -> None:
    priya.post("/leave-requests", json=leave())
    page = arjun.get("/notifications").json()
    assert page["total"] == 1
    assert page["items"][0]["event"] == "submitted"
    assert page["items"][0]["read"] is False


def test_unread_first_and_unread_filter(priya: TestClient, arjun: TestClient) -> None:
    priya.post("/leave-requests", json=leave(start="2026-11-16", end="2026-11-16"))
    priya.post("/leave-requests", json=leave(start="2026-11-17", end="2026-11-17"))
    first = arjun.get("/notifications").json()["items"][1]
    arjun.post(f"/notifications/{first['id']}/read")

    items = arjun.get("/notifications").json()["items"]
    assert [n["read"] for n in items] == [False, True]
    assert arjun.get("/notifications", params={"unread": True}).json()["total"] == 1


def test_cannot_mark_someone_elses_notification(
    priya: TestClient, arjun: TestClient
) -> None:
    priya.post("/leave-requests", json=leave())
    arjuns = arjun.get("/notifications").json()["items"][0]
    r = priya.post(f"/notifications/{arjuns['id']}/read")
    assert r.status_code == 404


def test_read_all(priya: TestClient, arjun: TestClient) -> None:
    priya.post("/leave-requests", json=leave(start="2026-11-16", end="2026-11-16"))
    priya.post("/leave-requests", json=leave(start="2026-11-17", end="2026-11-17"))
    assert arjun.post("/notifications/read-all").json() == {"marked_read": 2}
    assert arjun.get("/notifications", params={"unread": True}).json()["total"] == 0


def test_stream_requires_a_token(client: TestClient) -> None:
    assert client.get("/notifications/stream").status_code == 401


def test_live_subscriber_receives_new_notification(
    app: FastAPI, people: dict[str, Any]
) -> None:
    """What the SSE stream relies on: a subscriber's queue gets each new notification."""
    inbox = app.state.container.inbox

    async def scenario() -> Notification:
        queue = inbox.subscribe(people["arjun"])
        sent = Notification(
            recipient_id=people["arjun"],
            event=NotificationEvent.SUBMITTED,
            request_id=people["priya"],
            message="hello",
        )
        await inbox.send(sent)
        received: Notification = await asyncio.wait_for(queue.get(), timeout=1)
        inbox.unsubscribe(people["arjun"], queue)
        return received

    assert asyncio.run(scenario()).message == "hello"
