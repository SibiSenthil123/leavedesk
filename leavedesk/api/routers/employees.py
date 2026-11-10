"""GET /employees/{id}/balance: yourself, or someone who reports to you."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from leavedesk.api.deps import ContainerDep, CurrentUser
from leavedesk.api.schemas import BalanceOut, ErrorResponse
from leavedesk.domain.exceptions import PermissionDeniedError
from leavedesk.domain.models import LeaveType

router = APIRouter(prefix="/employees", tags=["employees"])


@router.get(
    "/{employee_id}/balance",
    response_model=list[BalanceOut],
    responses={403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def get_balance(
    employee_id: UUID, user: CurrentUser, container: ContainerDep
) -> list[BalanceOut]:
    employee = container.repo.get_employee(employee_id)  # 404 if unknown
    if employee.id != user.id and employee.manager_id != user.id:
        raise PermissionDeniedError(
            "you can only see your own or your reports' balance"
        )
    balances = [container.repo.get_balance(employee.id, t) for t in LeaveType]
    return [
        BalanceOut(
            leave_type=b.leave_type,
            entitled=b.entitled,
            used=b.used,
            remaining=b.remaining,
        )
        for b in balances
    ]
