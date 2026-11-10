"""Leave request endpoints. Each one is thin: check who is asking, call the domain
service, queue the notification, shape the response."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Query

from leavedesk.api.container import Container
from leavedesk.api.deps import (
    ContainerDep,
    CurrentUser,
    NotificationsDep,
    ServiceDep,
    direct_report_ids,
)
from leavedesk.api.schemas import (
    ErrorResponse,
    LeaveRequestCreate,
    LeaveRequestOut,
    LeaveSort,
    Page,
    RejectBody,
)
from leavedesk.domain.exceptions import NotFoundError
from leavedesk.domain.models import (
    Employee,
    LeaveRequest,
    LeaveStatus,
    NotificationEvent,
)

router = APIRouter(prefix="/leave-requests", tags=["leave requests"])

# Documents the error shape for these status codes on /docs.
ERRORS: dict[int | str, dict[str, Any]] = {
    code: {"model": ErrorResponse} for code in (401, 403, 404, 409, 422)
}


def _visible_ids(container: Container, user: Employee) -> set[UUID]:
    """You can see your own requests and those of people who report to you."""
    return {user.id} | direct_report_ids(container, user)


def _get_visible(
    container: Container, user: Employee, request_id: UUID
) -> LeaveRequest:
    request = container.repo.get_request(request_id)
    if request.employee_id not in _visible_ids(container, user):
        # 404, not 403: don't confirm that someone else's request exists.
        raise NotFoundError(f"leave request {request_id} not found")
    return request


@router.post("", status_code=201, response_model=LeaveRequestOut, responses=ERRORS)
async def apply_for_leave(
    body: LeaveRequestCreate,
    user: CurrentUser,
    service: ServiceDep,
    notifications: NotificationsDep,
    background: BackgroundTasks,
) -> LeaveRequest:
    request = LeaveRequest(employee_id=user.id, **body.model_dump())
    saved = await service.apply(request)
    background.add_task(notifications.notify, NotificationEvent.SUBMITTED, saved)
    return saved


@router.get("", response_model=Page[LeaveRequestOut], responses=ERRORS)
def list_leave_requests(
    user: CurrentUser,
    container: ContainerDep,
    status: LeaveStatus | None = None,
    employee_id: UUID | None = None,
    sort: LeaveSort = "-created_at",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[LeaveRequestOut]:
    ids = _visible_ids(container, user)
    if employee_id is not None:
        ids &= {employee_id}  # filtering to someone you can't see gives an empty list
    rows = [r for i in ids for r in container.repo.requests_for(i)]
    if status is not None:
        rows = [r for r in rows if r.status == status]
    field = sort.lstrip("-")
    rows.sort(key=lambda r: getattr(r, field), reverse=sort.startswith("-"))
    return Page[LeaveRequestOut](
        items=[
            LeaveRequestOut.model_validate(r) for r in rows[offset : offset + limit]
        ],
        total=len(rows),
        limit=limit,
        offset=offset,
    )


@router.get("/{request_id}", response_model=LeaveRequestOut, responses=ERRORS)
def get_leave_request(
    request_id: UUID, user: CurrentUser, container: ContainerDep
) -> LeaveRequest:
    return _get_visible(container, user, request_id)


@router.post("/{request_id}/approve", response_model=LeaveRequestOut, responses=ERRORS)
async def approve(
    request_id: UUID,
    user: CurrentUser,
    service: ServiceDep,
    notifications: NotificationsDep,
    background: BackgroundTasks,
) -> LeaveRequest:
    request = await service.approve(request_id, manager_id=user.id)
    background.add_task(notifications.notify, NotificationEvent.APPROVED, request)
    return request


@router.post("/{request_id}/reject", response_model=LeaveRequestOut, responses=ERRORS)
async def reject(
    request_id: UUID,
    body: RejectBody,
    user: CurrentUser,
    service: ServiceDep,
    notifications: NotificationsDep,
    background: BackgroundTasks,
) -> LeaveRequest:
    request = await service.reject(request_id, manager_id=user.id, reason=body.reason)
    background.add_task(notifications.notify, NotificationEvent.REJECTED, request)
    return request


@router.delete("/{request_id}", response_model=LeaveRequestOut, responses=ERRORS)
async def cancel(
    request_id: UUID,
    user: CurrentUser,
    container: ContainerDep,
    service: ServiceDep,
    notifications: NotificationsDep,
    background: BackgroundTasks,
) -> LeaveRequest:
    """Cancel your own request. Only PENDING requests can be cancelled."""
    _get_visible(container, user, request_id)  # 404 for requests you can't see
    request = await service.cancel(request_id, employee_id=user.id)
    background.add_task(notifications.notify, NotificationEvent.CANCELLED, request)
    return request
