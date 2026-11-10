"""FastAPI dependencies: how a route gets the container, the settings and the logged-in user."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Query, Request
from fastapi.security import OAuth2PasswordBearer

from leavedesk.api.config import Settings
from leavedesk.api.container import Container
from leavedesk.api.security import InvalidTokenError, decode_access_token
from leavedesk.domain.exceptions import NotFoundError
from leavedesk.domain.models import Employee
from leavedesk.domain.notifications import NotificationService
from leavedesk.domain.service import LeaveService

# tokenUrl powers the "Authorize" button on /docs.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_container(request: Request) -> Container:
    container: Container = request.app.state.container
    return container


def get_service(
    container: Annotated[Container, Depends(get_container)],
) -> LeaveService:
    return container.service


def get_notifications(
    container: Annotated[Container, Depends(get_container)],
) -> NotificationService:
    """Its own dependency so tests can swap in a mock with dependency_overrides."""
    return container.notifications


def _unauthorized(message: str = "not authenticated") -> HTTPException:
    return HTTPException(
        status_code=401, detail=message, headers={"WWW-Authenticate": "Bearer"}
    )


def _user_from_token(
    token: str | None, settings: Settings, container: Container
) -> Employee:
    if not token:
        raise _unauthorized()
    try:
        user_id = decode_access_token(token, settings)
        return container.repo.get_employee(user_id)
    except (InvalidTokenError, NotFoundError):
        raise _unauthorized("invalid or expired token") from None


def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    settings: Annotated[Settings, Depends(get_settings)],
    container: Annotated[Container, Depends(get_container)],
) -> Employee:
    return _user_from_token(token, settings, container)


def get_stream_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    settings: Annotated[Settings, Depends(get_settings)],
    container: Annotated[Container, Depends(get_container)],
    access_token: Annotated[str | None, Query()] = None,
) -> Employee:
    """Browsers' EventSource cannot send headers, so the SSE stream also takes ?access_token=."""
    return _user_from_token(token or access_token, settings, container)


def direct_report_ids(container: Container, manager: Employee) -> set[UUID]:
    return {e.id for e in container.repo.all_employees() if e.manager_id == manager.id}


CurrentUser = Annotated[Employee, Depends(get_current_user)]
ContainerDep = Annotated[Container, Depends(get_container)]
ServiceDep = Annotated[LeaveService, Depends(get_service)]
NotificationsDep = Annotated[NotificationService, Depends(get_notifications)]
