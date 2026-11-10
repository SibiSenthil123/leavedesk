"""Storage behind an interface. Day 3 swaps InMemory for PostgreSQL without touching the service."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from leavedesk.domain.balance import LeaveBalance
from leavedesk.domain.exceptions import NotFoundError
from leavedesk.domain.models import Employee, LeaveRequest, LeaveType


class LeaveRepository(Protocol):
    """What the service needs from storage. Any class with these methods qualifies."""

    def add_employee(self, employee: Employee) -> None: ...
    def get_employee(self, employee_id: UUID) -> Employee: ...
    def set_balance(self, balance: LeaveBalance) -> None: ...
    def get_balance(self, employee_id: UUID, leave_type: LeaveType) -> LeaveBalance: ...
    def add_request(self, request: LeaveRequest) -> None: ...
    def get_request(self, request_id: UUID) -> LeaveRequest: ...
    def requests_for(self, employee_id: UUID) -> list[LeaveRequest]: ...


class InMemoryLeaveRepository:
    """Dict-backed repository. Note: it does not inherit from LeaveRepository."""

    def __init__(self) -> None:
        self._employees: dict[UUID, Employee] = {}
        self._balances: dict[tuple[UUID, LeaveType], LeaveBalance] = {}
        self._requests: dict[UUID, LeaveRequest] = {}

    def add_employee(self, employee: Employee) -> None:
        self._employees[employee.id] = employee

    def get_employee(self, employee_id: UUID) -> Employee:
        try:
            return self._employees[employee_id]
        except KeyError:
            raise NotFoundError(f"employee {employee_id} not found") from None

    def set_balance(self, balance: LeaveBalance) -> None:
        self._balances[(balance.employee_id, balance.leave_type)] = balance

    def get_balance(self, employee_id: UUID, leave_type: LeaveType) -> LeaveBalance:
        try:
            return self._balances[(employee_id, leave_type)]
        except KeyError:
            raise NotFoundError(f"no {leave_type} balance for {employee_id}") from None

    def add_request(self, request: LeaveRequest) -> None:
        self._requests[request.id] = request

    def get_request(self, request_id: UUID) -> LeaveRequest:
        try:
            return self._requests[request_id]
        except KeyError:
            raise NotFoundError(f"leave request {request_id} not found") from None

    def requests_for(self, employee_id: UUID) -> list[LeaveRequest]:
        return [r for r in self._requests.values() if r.employee_id == employee_id]
