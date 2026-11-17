"""Storage behind an interface. Day 3 adds a PostgreSQL version (leavedesk/db/repository.py)
without changing what the service asks for."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from typing import Protocol
from uuid import UUID

from leavedesk.domain.balance import LeaveBalance
from leavedesk.domain.exceptions import NotFoundError
from leavedesk.domain.models import Employee, LeaveRequest, LeaveType, NotificationEvent


class LeaveRepository(Protocol):
    """What the service needs from storage. Any class with these methods qualifies."""

    def unit_of_work(self) -> AbstractContextManager[None]: ...
    def add_employee(self, employee: Employee) -> None: ...
    def get_employee(self, employee_id: UUID) -> Employee: ...
    def find_employee_by_email(self, email: str) -> Employee | None: ...
    def set_balance(self, balance: LeaveBalance) -> None: ...
    def get_balance(
        self, employee_id: UUID, leave_type: LeaveType, for_update: bool = False
    ) -> LeaveBalance: ...
    def record_deduction(
        self, balance: LeaveBalance, days: float, request_id: UUID
    ) -> None: ...
    def add_request(self, request: LeaveRequest) -> None: ...
    def get_request(
        self, request_id: UUID, for_update: bool = False
    ) -> LeaveRequest: ...
    def save_request(self, request: LeaveRequest) -> None: ...
    def requests_for(self, employee_id: UUID) -> list[LeaveRequest]: ...
    def all_employees(self) -> list[Employee]: ...
    def add_outbox(self, event: NotificationEvent, request_id: UUID) -> None: ...


class InMemoryLeaveRepository:
    """Dict-backed repository. Note: it does not inherit from LeaveRepository."""

    def __init__(self) -> None:
        self._employees: dict[UUID, Employee] = {}
        self._balances: dict[tuple[UUID, LeaveType], LeaveBalance] = {}
        self._requests: dict[UUID, LeaveRequest] = {}
        self.outbox: list[tuple[NotificationEvent, UUID]] = []

    @contextmanager
    def unit_of_work(self) -> Iterator[None]:
        # Dicts have no transactions; PostgreSQL's version opens one here.
        yield

    def add_employee(self, employee: Employee) -> None:
        self._employees[employee.id] = employee

    def get_employee(self, employee_id: UUID) -> Employee:
        try:
            return self._employees[employee_id]
        except KeyError:
            raise NotFoundError(f"employee {employee_id} not found") from None

    def find_employee_by_email(self, email: str) -> Employee | None:
        wanted = email.strip().lower()
        return next(
            (e for e in self._employees.values() if e.email.lower() == wanted), None
        )

    def set_balance(self, balance: LeaveBalance) -> None:
        self._balances[(balance.employee_id, balance.leave_type)] = balance

    def get_balance(
        self, employee_id: UUID, leave_type: LeaveType, for_update: bool = False
    ) -> LeaveBalance:
        try:
            return self._balances[(employee_id, leave_type)]
        except KeyError:
            raise NotFoundError(f"no {leave_type} balance for {employee_id}") from None

    def record_deduction(
        self, balance: LeaveBalance, days: float, request_id: UUID
    ) -> None:
        self._balances[(balance.employee_id, balance.leave_type)] = balance

    def add_request(self, request: LeaveRequest) -> None:
        self._requests[request.id] = request

    def get_request(self, request_id: UUID, for_update: bool = False) -> LeaveRequest:
        try:
            return self._requests[request_id]
        except KeyError:
            raise NotFoundError(f"leave request {request_id} not found") from None

    def save_request(self, request: LeaveRequest) -> None:
        self._requests[request.id] = request

    def requests_for(self, employee_id: UUID) -> list[LeaveRequest]:
        return [r for r in self._requests.values() if r.employee_id == employee_id]

    def all_employees(self) -> list[Employee]:
        return list(self._employees.values())

    def add_outbox(self, event: NotificationEvent, request_id: UUID) -> None:
        self.outbox.append((event, request_id))
