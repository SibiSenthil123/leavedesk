"""In-app notifications: list, mark read, and a live Server-Sent Events stream."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse

from leavedesk.api.deps import ContainerDep, CurrentUser, get_stream_user
from leavedesk.api.schemas import ErrorResponse, NotificationOut, Page, ReadAllResult
from leavedesk.domain.exceptions import NotFoundError
from leavedesk.domain.models import Employee, Notification

router = APIRouter(prefix="/notifications", tags=["notifications"])

KEEP_ALIVE_SECONDS = 15.0


@router.get("", response_model=Page[NotificationOut])
def list_notifications(
    user: CurrentUser,
    container: ContainerDep,
    unread: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[NotificationOut]:
    """Unread first, newest first within each group. `?unread=true` shows only unread."""
    rows = container.inbox.for_user(user.id)
    if unread:
        rows = [n for n in rows if not n.read]
    rows.sort(key=lambda n: n.created_at, reverse=True)
    rows.sort(key=lambda n: n.read)  # stable sort: False (unread) comes first
    return Page[NotificationOut](
        items=[
            NotificationOut.model_validate(n) for n in rows[offset : offset + limit]
        ],
        total=len(rows),
        limit=limit,
        offset=offset,
    )


@router.post("/read-all", response_model=ReadAllResult)
def mark_all_read(user: CurrentUser, container: ContainerDep) -> ReadAllResult:
    unread = [n for n in container.inbox.for_user(user.id) if not n.read]
    for n in unread:
        n.read = True
    return ReadAllResult(marked_read=len(unread))


@router.post(
    "/{notification_id}/read",
    response_model=NotificationOut,
    responses={404: {"model": ErrorResponse}},
)
def mark_read(
    notification_id: UUID, user: CurrentUser, container: ContainerDep
) -> Notification:
    for n in container.inbox.for_user(user.id):  # only searches YOUR inbox
        if n.id == notification_id:
            n.read = True
            return n
    raise NotFoundError(f"notification {notification_id} not found")


def sse_message(notification: Notification) -> str:
    """One SSE frame: an event name, a JSON data line, then a blank line."""
    data = NotificationOut.model_validate(notification).model_dump_json()
    return f"event: notification\nid: {notification.id}\ndata: {data}\n\n"


@router.get("/stream", response_class=StreamingResponse)
async def stream(
    request: Request,
    user: Annotated[Employee, Depends(get_stream_user)],
    container: ContainerDep,
) -> StreamingResponse:
    """Server-Sent Events. Each new notification for you arrives as an `event: notification`.
    Browsers: `new EventSource('/notifications/stream?access_token=...')`."""
    queue = container.inbox.subscribe(user.id)

    async def events() -> AsyncIterator[str]:
        try:
            yield ": connected\n\n"  # lines starting with ':' are comments
            while not await request.is_disconnected():
                try:
                    notification = await asyncio.wait_for(
                        queue.get(), timeout=KEEP_ALIVE_SECONDS
                    )
                except TimeoutError:
                    yield ": keep-alive\n\n"  # stops proxies closing an idle connection
                    continue
                yield sse_message(notification)
        finally:
            container.inbox.unsubscribe(user.id, queue)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
