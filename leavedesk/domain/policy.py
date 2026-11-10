"""Leave policies: inheritance fits here, because every policy IS A LeavePolicy."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from leavedesk.domain.balance import LeaveBalance
from leavedesk.domain.exceptions import PolicyViolationError
from leavedesk.domain.models import LeaveRequest, LeaveType


class LeavePolicy(ABC):
    """Contract every leave type follows. Shared checks live here, special ones in subclasses."""

    leave_type: LeaveType

    def validate(
        self, request: LeaveRequest, days: float, balance: LeaveBalance, today: date
    ) -> None:
        """Raise a LeaveDeskError if the request breaks this policy."""
        if days <= 0:
            raise PolicyViolationError("the selected range contains no working days")
        balance.ensure_available(days)
        self.extra_rules(request, days, today)

    @abstractmethod
    def extra_rules(self, request: LeaveRequest, days: float, today: date) -> None:
        """Rules specific to one leave type."""


class AnnualLeavePolicy(LeavePolicy):
    """Annual leave is planned: it cannot start in the past."""

    leave_type = LeaveType.ANNUAL

    def extra_rules(self, request: LeaveRequest, days: float, today: date) -> None:
        if request.start < today:
            raise PolicyViolationError("annual leave cannot start in the past")


class SickLeavePolicy(LeavePolicy):
    """Sick leave can be backdated up to 7 days, but not booked far ahead."""

    leave_type = LeaveType.SICK
    MAX_BACKDATE_DAYS = 7
    MAX_AHEAD_DAYS = 2

    def extra_rules(self, request: LeaveRequest, days: float, today: date) -> None:
        if (today - request.start).days > self.MAX_BACKDATE_DAYS:
            raise PolicyViolationError(
                f"sick leave can be backdated at most {self.MAX_BACKDATE_DAYS} days"
            )
        if (request.start - today).days > self.MAX_AHEAD_DAYS:
            raise PolicyViolationError(
                f"sick leave cannot start more than {self.MAX_AHEAD_DAYS} days ahead"
            )


class CasualLeavePolicy(LeavePolicy):
    """Casual leave is for short absences: at most 2 working days per request."""

    leave_type = LeaveType.CASUAL
    MAX_DAYS = 2

    def extra_rules(self, request: LeaveRequest, days: float, today: date) -> None:
        if days > self.MAX_DAYS:
            raise PolicyViolationError(
                f"casual leave is limited to {self.MAX_DAYS} days per request"
            )


def default_policies() -> dict[LeaveType, LeavePolicy]:
    return {
        p.leave_type: p
        for p in (AnnualLeavePolicy(), SickLeavePolicy(), CasualLeavePolicy())
    }
