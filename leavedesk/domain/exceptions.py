"""Business rule violations. Each one maps to an HTTP error on Day 2."""

from __future__ import annotations


class LeaveDeskError(Exception):
    """Base class for every LeaveDesk business rule violation."""


class InsufficientBalanceError(LeaveDeskError):
    """The employee does not have enough days left for this leave type."""

    def __init__(self, leave_type: str, requested: float, available: float) -> None:
        super().__init__(
            f"{leave_type}: requested {requested} day(s), only {available} available"
        )
        self.leave_type = leave_type
        self.requested = requested
        self.available = available


class OverlappingLeaveError(LeaveDeskError):
    """The new request overlaps a pending or approved request of the same employee."""

    def __init__(self, existing_id: object) -> None:
        super().__init__(f"overlaps existing request {existing_id}")
        self.existing_id = existing_id


class InvalidTransitionError(LeaveDeskError):
    """A status change that the state machine does not allow."""

    def __init__(self, current: str, target: str) -> None:
        super().__init__(f"cannot move a request from {current} to {target}")
        self.current = current
        self.target = target


class NotFoundError(LeaveDeskError):
    """An employee or request id that does not exist."""


class PermissionDeniedError(LeaveDeskError):
    """The acting user is not allowed to do this (e.g. not the employee's manager)."""


class PolicyViolationError(LeaveDeskError):
    """A leave-type specific rule was broken (e.g. annual leave needs notice)."""
