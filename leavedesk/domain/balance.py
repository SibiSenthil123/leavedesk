"""LeaveBalance: internal state that only our code creates, so a dataclass is enough."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from leavedesk.domain.exceptions import InsufficientBalanceError
from leavedesk.domain.models import LeaveType


@dataclass
class LeaveBalance:
    employee_id: UUID
    leave_type: LeaveType
    entitled: float
    used: float = 0.0

    @property
    def remaining(self) -> float:
        return self.entitled - self.used

    def ensure_available(self, days: float) -> None:
        if days > self.remaining:
            raise InsufficientBalanceError(self.leave_type, days, self.remaining)

    def deduct(self, days: float) -> None:
        self.ensure_available(days)
        self.used += days
