"""Builds every object the API needs, once, and keeps them together."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from leavedesk.api.config import Settings
from leavedesk.api.users import InMemoryUserStore
from leavedesk.domain.notifications import (
    EmailNotifier,
    InAppNotifier,
    NotificationService,
)
from leavedesk.domain.policy import default_policies
from leavedesk.domain.repository import InMemoryLeaveRepository, LeaveRepository
from leavedesk.domain.service import LeaveService


@dataclass
class Container:
    repo: LeaveRepository
    users: InMemoryUserStore
    inbox: InAppNotifier
    notifications: NotificationService
    service: LeaveService


def build_container(
    settings: Settings, today: Callable[[], date] = date.today
) -> Container:
    repo = InMemoryLeaveRepository()
    inbox = InAppNotifier()
    notifications = NotificationService(
        repo, [EmailNotifier(repo, delay_seconds=settings.email_delay_seconds), inbox]
    )
    # notifications=None: the service does not send them itself. The routes queue
    # them as BackgroundTasks so the HTTP response is not kept waiting.
    service = LeaveService(repo, default_policies(), notifications=None, today=today)
    return Container(repo, InMemoryUserStore(), inbox, notifications, service)
