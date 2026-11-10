from typing import Any
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from leavedesk.domain.models import NotificationEvent
from tests.conftest import leave


def apply(client: TestClient, **overrides: Any) -> dict[str, Any]:
    r = client.post("/leave-requests", json=leave(**overrides))
    assert r.status_code == 201, r.text
    body: dict[str, Any] = r.json()
    return body


# ---- apply ---------------------------------------------------------------


def test_apply_creates_pending_request_and_queues_notification(
    priya: TestClient, notifier: AsyncMock, people: dict[str, Any]
) -> None:
    body = apply(priya)
    assert body["status"] == "PENDING"
    assert body["employee_id"] == str(people["priya"])  # from the token, not the body
    notifier.notify.assert_awaited_once()
    event, request = notifier.notify.await_args.args
    assert event == NotificationEvent.SUBMITTED
    assert str(request.id) == body["id"]


def test_overlapping_request_is_409(priya: TestClient, notifier: AsyncMock) -> None:
    apply(priya)
    r = priya.post("/leave-requests", json=leave(start="2026-11-19", end="2026-11-24"))
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "OVERLAPPING_LEAVE"


def test_end_before_start_is_422(priya: TestClient) -> None:
    r = priya.post("/leave-requests", json=leave(start="2026-11-20", end="2026-11-16"))
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_more_days_than_balance_is_422(priya: TestClient) -> None:
    # Casual balance is 6, but casual is also capped at 2 per request, so use annual (18).
    r = priya.post("/leave-requests", json=leave(start="2026-11-16", end="2026-12-11"))
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "INSUFFICIENT_BALANCE"


def test_weekend_only_range_is_422(priya: TestClient) -> None:
    r = priya.post("/leave-requests", json=leave(start="2026-11-14", end="2026-11-15"))
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "POLICY_VIOLATION"


def test_client_cannot_choose_employee_id(
    priya: TestClient, people: dict[str, Any]
) -> None:
    r = priya.post("/leave-requests", json=leave(employee_id=str(people["kiran"])))
    assert r.status_code == 422  # extra fields are forbidden


# ---- read ----------------------------------------------------------------


def test_unknown_request_is_404_with_error_shape(priya: TestClient) -> None:
    r = priya.get("/leave-requests/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404
    error = r.json()["error"]
    assert error["code"] == "NOT_FOUND"
    assert error["request_id"] == r.headers["X-Request-ID"]


def test_colleague_cannot_see_my_request(
    priya: TestClient, kiran: TestClient, notifier: AsyncMock
) -> None:
    created = apply(priya)
    assert kiran.get(f"/leave-requests/{created['id']}").status_code == 404


def test_list_filters_sorts_and_paginates(
    priya: TestClient, arjun: TestClient, notifier: AsyncMock
) -> None:
    first = apply(priya, start="2026-11-16", end="2026-11-16")
    apply(priya, start="2026-11-17", end="2026-11-17")
    apply(priya, start="2026-11-18", end="2026-11-18")
    arjun.post(f"/leave-requests/{first['id']}/approve")

    page = priya.get("/leave-requests", params={"sort": "start", "limit": 2}).json()
    assert page["total"] == 3
    assert [r["start"] for r in page["items"]] == ["2026-11-16", "2026-11-17"]

    pending = priya.get("/leave-requests", params={"status": "PENDING"}).json()
    assert pending["total"] == 2


def test_manager_sees_reports_requests(
    priya: TestClient, arjun: TestClient, people: dict[str, Any], notifier: AsyncMock
) -> None:
    apply(priya)
    r = arjun.get("/leave-requests", params={"employee_id": str(people["priya"])})
    assert r.json()["total"] == 1


# ---- approve / reject / cancel ------------------------------------------


def test_manager_approves_and_balance_drops(
    priya: TestClient, arjun: TestClient, people: dict[str, Any], notifier: AsyncMock
) -> None:
    created = apply(priya)
    r = arjun.post(f"/leave-requests/{created['id']}/approve")
    assert r.status_code == 200
    assert r.json()["status"] == "APPROVED"
    assert notifier.notify.await_args.args[0] == NotificationEvent.APPROVED

    balances = priya.get(f"/employees/{people['priya']}/balance").json()
    annual = next(b for b in balances if b["leave_type"] == "ANNUAL")
    assert annual["used"] == 5
    assert annual["remaining"] == 13


def test_non_manager_cannot_approve(
    priya: TestClient, kiran: TestClient, notifier: AsyncMock
) -> None:
    created = apply(priya)
    r = kiran.post(f"/leave-requests/{created['id']}/approve")
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "FORBIDDEN"


def test_approving_twice_is_409(
    priya: TestClient, arjun: TestClient, notifier: AsyncMock
) -> None:
    created = apply(priya)
    arjun.post(f"/leave-requests/{created['id']}/approve")
    r = arjun.post(f"/leave-requests/{created['id']}/approve")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "INVALID_TRANSITION"


def test_reject_stores_reason(
    priya: TestClient, arjun: TestClient, notifier: AsyncMock
) -> None:
    created = apply(priya)
    r = arjun.post(
        f"/leave-requests/{created['id']}/reject", json={"reason": "Release week"}
    )
    assert r.status_code == 200
    assert r.json()["status"] == "REJECTED"
    assert r.json()["rejection_reason"] == "Release week"
    assert notifier.notify.await_args.args[0] == NotificationEvent.REJECTED


def test_reject_with_short_reason_is_422(
    priya: TestClient, arjun: TestClient, notifier: AsyncMock
) -> None:
    created = apply(priya)
    r = arjun.post(f"/leave-requests/{created['id']}/reject", json={"reason": " no "})
    assert r.status_code == 422


def test_cancel_pending_request(priya: TestClient, notifier: AsyncMock) -> None:
    created = apply(priya)
    r = priya.delete(f"/leave-requests/{created['id']}")
    assert r.status_code == 200
    assert r.json()["status"] == "CANCELLED"
    assert notifier.notify.await_args.args[0] == NotificationEvent.CANCELLED


def test_cancel_approved_request_is_409(
    priya: TestClient, arjun: TestClient, notifier: AsyncMock
) -> None:
    created = apply(priya)
    arjun.post(f"/leave-requests/{created['id']}/approve")
    assert priya.delete(f"/leave-requests/{created['id']}").status_code == 409


def test_manager_cannot_cancel_for_employee(
    priya: TestClient, arjun: TestClient, notifier: AsyncMock
) -> None:
    created = apply(priya)
    assert arjun.delete(f"/leave-requests/{created['id']}").status_code == 403
