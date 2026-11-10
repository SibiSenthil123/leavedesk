"""Notifications: who is told what, sent through every channel concurrently."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from uuid import UUID

from leavedesk.domain.models import LeaveRequest, Notification, NotificationEvent
from leavedesk.domain.repository import LeaveRepository


class Notifier(ABC):
    """One delivery channel (email, in-app, later SMS or push)."""

    @abstractmethod
    async def send(self, notification: Notification) -> None: ...


class EmailNotifier(Notifier):
    """Stub: pretends to call an SMTP server."""

    def __init__(self, repo: LeaveRepository, delay_seconds: float = 0.2) -> None:
        self.repo = repo
        self.delay_seconds = delay_seconds
        self.sent: list[Notification] = []

    async def send(self, notification: Notification) -> None:
        await asyncio.sleep(self.delay_seconds)  # stands in for network I/O
        recipient = self.repo.get_employee(notification.recipient_id)
        self.sent.append(notification)
        print(f"    [email -> {recipient.email}] {notification.message}")


class InAppNotifier(Notifier):
    """Keeps an inbox per user; the Day 4 bell icon reads from this."""

    def __init__(self) -> None:
        self.inbox: dict[UUID, list[Notification]] = {}

    async def send(self, notification: Notification) -> None:
        self.inbox.setdefault(notification.recipient_id, []).append(notification)

    def unread_count(self, user_id: UUID) -> int:
        return sum(1 for n in self.inbox.get(user_id, []) if not n.read)


class NotificationService:
    """Decides recipients per event and fans out to every notifier at once."""

    def __init__(self, repo: LeaveRepository, notifiers: list[Notifier]) -> None:
        self.repo = repo
        self.notifiers = notifiers

    def recipients(self, event: NotificationEvent, request: LeaveRequest) -> list[UUID]:
        employee = self.repo.get_employee(request.employee_id)
        if event in (NotificationEvent.SUBMITTED, NotificationEvent.CANCELLED):
            return [employee.manager_id] if employee.manager_id else []
        return [employee.id]  # approved / rejected -> the employee

    def message(self, event: NotificationEvent, request: LeaveRequest) -> str:
        employee = self.repo.get_employee(request.employee_id)
        span = f"{request.start:%d %b} to {request.end:%d %b %Y}"
        texts = {
            NotificationEvent.SUBMITTED: f"{employee.name} requested {request.leave_type} leave, {span}",
            NotificationEvent.APPROVED: f"Your {request.leave_type} leave, {span}, was approved",
            NotificationEvent.REJECTED: f"Your {request.leave_type} leave, {span}, was rejected: {request.rejection_reason}",
            NotificationEvent.CANCELLED: f"{employee.name} cancelled {request.leave_type} leave, {span}",
        }
        return texts[event]

    async def notify(
        self, event: NotificationEvent, request: LeaveRequest
    ) -> list[Notification]:
        notifications = [
            Notification(
                recipient_id=rid,
                event=event,
                request_id=request.id,
                message=self.message(event, request),
            )
            for rid in self.recipients(event, request)
        ]
        # Every (notifier, notification) pair runs concurrently: total time ~ the slowest send.
        await asyncio.gather(
            *(notifier.send(n) for notifier in self.notifiers for n in notifications)
        )
        return notifications
