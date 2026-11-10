"""LeaveService: the use cases. Composition fits here: it HAS a repository, policies and a notifier."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from uuid import UUID

from leavedesk.domain.audit import audit
from leavedesk.domain.calendar import ranges_overlap, working_days
from leavedesk.domain.exceptions import (
    InvalidTransitionError,
    OverlappingLeaveError,
    PermissionDeniedError,
)
from leavedesk.domain.models import (
    LeaveRequest,
    LeaveStatus,
    LeaveType,
    NotificationEvent,
)
from leavedesk.domain.notifications import NotificationService
from leavedesk.domain.policy import LeavePolicy
from leavedesk.domain.repository import LeaveRepository

# The state machine: which status may move to which. Anything else is invalid.
ALLOWED_TRANSITIONS: dict[LeaveStatus, set[LeaveStatus]] = {
    LeaveStatus.PENDING: {
        LeaveStatus.APPROVED,
        LeaveStatus.REJECTED,
        LeaveStatus.CANCELLED,
    },
    LeaveStatus.APPROVED: set(),
    LeaveStatus.REJECTED: set(),
    LeaveStatus.CANCELLED: set(),
}

ACTIVE_STATUSES = {LeaveStatus.PENDING, LeaveStatus.APPROVED}


class LeaveService:
    def __init__(
        self,
        repo: LeaveRepository,
        policies: dict[LeaveType, LeavePolicy],
        notifications: NotificationService,
        today: Callable[[], date] = date.today,
    ) -> None:
        self.repo = repo
        self.policies = policies
        self.notifications = notifications
        self.today = today  # injected so the demo and tests control "today"

    @audit
    async def apply(self, request: LeaveRequest) -> LeaveRequest:
        """Validate and store a new PENDING request, then notify the manager."""
        self.repo.get_employee(request.employee_id)  # NotFoundError if unknown
        days = working_days(request.start, request.end, request.half_day)
        self._check_overlap(request)
        balance = self.repo.get_balance(request.employee_id, request.leave_type)
        self.policies[request.leave_type].validate(request, days, balance, self.today())
        self.repo.add_request(request)
        await self.notifications.notify(NotificationEvent.SUBMITTED, request)
        return request

    @audit
    async def approve(self, request_id: UUID, manager_id: UUID) -> LeaveRequest:
        """Manager approves: re-check balance, deduct it, notify the employee."""
        request = self.repo.get_request(request_id)
        self._ensure_manager_of(request, manager_id)
        self._ensure_transition(request, LeaveStatus.APPROVED)
        days = working_days(request.start, request.end, request.half_day)
        balance = self.repo.get_balance(request.employee_id, request.leave_type)
        balance.deduct(days)  # raises InsufficientBalanceError if it ran out meanwhile
        request.status = LeaveStatus.APPROVED
        await self.notifications.notify(NotificationEvent.APPROVED, request)
        return request

    @audit
    async def reject(
        self, request_id: UUID, manager_id: UUID, reason: str
    ) -> LeaveRequest:
        request = self.repo.get_request(request_id)
        self._ensure_manager_of(request, manager_id)
        self._ensure_transition(request, LeaveStatus.REJECTED)
        if len(reason.strip()) < 5:
            raise ValueError("a rejection needs a reason of at least 5 characters")
        request.rejection_reason = reason.strip()
        request.status = LeaveStatus.REJECTED
        await self.notifications.notify(NotificationEvent.REJECTED, request)
        return request

    @audit
    async def cancel(self, request_id: UUID, employee_id: UUID) -> LeaveRequest:
        """Only the owner can cancel, and only while it is still PENDING."""
        request = self.repo.get_request(request_id)
        if request.employee_id != employee_id:
            raise PermissionDeniedError("only the employee who applied can cancel")
        self._ensure_transition(request, LeaveStatus.CANCELLED)
        request.status = LeaveStatus.CANCELLED
        await self.notifications.notify(NotificationEvent.CANCELLED, request)
        return request

    # ---- private helpers -------------------------------------------------

    def _check_overlap(self, new: LeaveRequest) -> None:
        for existing in self.repo.requests_for(new.employee_id):
            if existing.status in ACTIVE_STATUSES and ranges_overlap(
                new.start, new.end, existing.start, existing.end
            ):
                raise OverlappingLeaveError(existing.id)

    def _ensure_manager_of(self, request: LeaveRequest, manager_id: UUID) -> None:
        employee = self.repo.get_employee(request.employee_id)
        if employee.manager_id != manager_id:
            raise PermissionDeniedError("only the employee's manager can do this")

    @staticmethod
    def _ensure_transition(request: LeaveRequest, target: LeaveStatus) -> None:
        if target not in ALLOWED_TRANSITIONS[request.status]:
            raise InvalidTransitionError(request.status, target)
