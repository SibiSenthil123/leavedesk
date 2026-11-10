from typing import Any

from fastapi.testclient import TestClient


def test_employee_sees_own_balance(priya: TestClient, people: dict[str, Any]) -> None:
    r = priya.get(f"/employees/{people['priya']}/balance")
    assert r.status_code == 200
    assert {b["leave_type"] for b in r.json()} == {"ANNUAL", "SICK", "CASUAL"}


def test_manager_sees_report_balance(arjun: TestClient, people: dict[str, Any]) -> None:
    assert arjun.get(f"/employees/{people['priya']}/balance").status_code == 200


def test_colleague_balance_is_403(priya: TestClient, people: dict[str, Any]) -> None:
    r = priya.get(f"/employees/{people['kiran']}/balance")
    assert r.status_code == 403


def test_employee_cannot_see_manager_balance(
    priya: TestClient, people: dict[str, Any]
) -> None:
    assert priya.get(f"/employees/{people['arjun']}/balance").status_code == 403
