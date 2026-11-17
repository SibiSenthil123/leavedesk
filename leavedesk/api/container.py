"""Builds every object the API needs, once, and keeps them together."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from sqlalchemy import Engine

from leavedesk.api.config import Settings
from leavedesk.api.users import InMemoryUserStore
from leavedesk.db.engine import make_engine, make_session_factory
from leavedesk.db.repository import SqlAlchemyLeaveRepository
from leavedesk.domain.notifications import InAppNotifier, NotificationService
from leavedesk.domain.policy import default_policies
from leavedesk.domain.repository import LeaveRepository
from leavedesk.domain.service import LeaveService


@dataclass
class Container:
    engine: Engine
    repo: LeaveRepository
    users: InMemoryUserStore
    inbox: InAppNotifier
    notifications: NotificationService
    service: LeaveService


def build_container(
    settings: Settings, today: Callable[[], date] = date.today
) -> Container:
    engine = make_engine(settings)
    repo = SqlAlchemyLeaveRepository(make_session_factory(engine))
    inbox = InAppNotifier()
    # In-app messages go out straight away (fast, live). Email now goes through the
    # outbox table and the worker (leavedesk/worker.py), so it can't get lost.
    notifications = NotificationService(repo, [inbox])
    # notifications=None: the service does not send them itself. The routes queue
    # them as BackgroundTasks so the HTTP response is not kept waiting.
    service = LeaveService(repo, default_policies(), notifications=None, today=today)
    return Container(engine, repo, InMemoryUserStore(), inbox, notifications, service)
