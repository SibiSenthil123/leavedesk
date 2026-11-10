"""Run with: python -m leavedesk.demo

Plays the happy path, then every edge case from SPEC.md, printing PASS or FAIL.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from collections.abc import Awaitable, Callable
from datetime import date
from typing import Any

from pydantic import ValidationError

from leavedesk.domain.audit import timed
from leavedesk.domain.balance import LeaveBalance
from leavedesk.domain.calendar import working_days
from leavedesk.domain.exceptions import (
    InsufficientBalanceError,
    InvalidTransitionError,
    OverlappingLeaveError,
    PermissionDeniedError,
    PolicyViolationError,
)
from leavedesk.domain.models import Employee, LeaveRequest, LeaveType, NotificationEvent
from leavedesk.domain.notifications import (
    EmailNotifier,
    InAppNotifier,
    NotificationService,
)
from leavedesk.domain.policy import default_policies
from leavedesk.domain.repository import InMemoryLeaveRepository
from leavedesk.domain.service import LeaveService

TODAY = date(2026, 11, 2)  # a fixed "today" (a Monday) so the output never changes

results: list[bool] = []


async def expect(
    label: str, exc_type: type[Exception], action: Callable[[], Any]
) -> None:
    """Run action; PASS if it raises exc_type, FAIL otherwise."""
    try:
        outcome = action()
        if isinstance(outcome, Awaitable):
            await outcome
    except exc_type as exc:
        detail = (
            exc.errors()[0]["msg"] if isinstance(exc, ValidationError) else str(exc)
        )
        print(f"  PASS  {label}\n        -> {type(exc).__name__}: {detail}")
        results.append(True)
        return
    print(f"  FAIL  {label}: expected {exc_type.__name__}, nothing raised")
    results.append(False)


def check(label: str, condition: bool, detail: str) -> None:
    print(f"  {'PASS' if condition else 'FAIL'}  {label}\n        -> {detail}")
    results.append(condition)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="        [audit] %(message)s", stream=sys.stdout
    )

    # ---- setup ------------------------------------------------------------
    repo = InMemoryLeaveRepository()
    manager = Employee(name="Meena Iyer", email="meena@acme.test")
    priya = Employee(
        name="Priya Sharma", email="priya@acme.test", manager_id=manager.id
    )
    for person in (manager, priya):
        repo.add_employee(person)
    for leave_type, days in (
        (LeaveType.ANNUAL, 10),
        (LeaveType.SICK, 5),
        (LeaveType.CASUAL, 4),
    ):
        repo.set_balance(LeaveBalance(priya.id, leave_type, entitled=days))

    email = EmailNotifier(repo)
    in_app = InAppNotifier()
    notifications = NotificationService(repo, [email, in_app])
    service = LeaveService(repo, default_policies(), notifications, today=lambda: TODAY)

    def new_request(start: date, end: date, **extra: Any) -> LeaveRequest:
        fields: dict[str, Any] = {
            "leave_type": LeaveType.ANNUAL,
            "reason": "Family trip",
        } | extra
        return LeaveRequest(employee_id=priya.id, start=start, end=end, **fields)

    annual = repo.get_balance(priya.id, LeaveType.ANNUAL)

    # ---- happy path -------------------------------------------------------
    print("\nHAPPY PATH")
    with timed("happy path"):
        print(f"  Priya's annual balance: {annual.remaining}")
        trip = await service.apply(new_request(date(2026, 11, 9), date(2026, 11, 13)))
        print(f"  Applied   {trip.start} to {trip.end}: status {trip.status}")
        await service.approve(trip.id, manager.id)
        print(f"  Approved  by {manager.name}: status {trip.status}")
        print(
            f"  Priya's annual balance: {annual.remaining}  (5 working days deducted)"
        )

        dentist = await service.apply(
            new_request(
                date(2026, 11, 20),
                date(2026, 11, 20),
                half_day=True,
                reason="Dentist visit",
            )
        )
        await service.reject(dentist.id, manager.id, reason="Team offsite that day")
        print(f"  Half day 20 Nov rejected: {dentist.rejection_reason}")

        errand = await service.apply(
            new_request(
                date(2026, 11, 26),
                date(2026, 11, 26),
                leave_type=LeaveType.CASUAL,
                reason="Bank errand",
            )
        )
        await service.cancel(errand.id, priya.id)
        print(f"  Casual 26 Nov cancelled by Priya: status {errand.status}")

    print(f"  Priya's unread in-app notifications:   {in_app.unread_count(priya.id)}")
    print(f"  Meena's unread in-app notifications:   {in_app.unread_count(manager.id)}")

    # ---- concurrency check --------------------------------------------------
    print("\nCONCURRENT NOTIFICATIONS")
    loop = asyncio.get_running_loop()
    started = loop.time()
    # 1 recipient x 2 notifiers; the email stub sleeps 0.2 s. Sequential would take longer.
    await notifications.notify(NotificationEvent.APPROVED, trip)
    elapsed = loop.time() - started
    check(
        "sends run concurrently with asyncio.gather",
        elapsed < 0.35,
        f"took {elapsed:.2f} s",
    )

    # ---- edge cases from SPEC.md -------------------------------------------
    print("\nEDGE CASES")
    await expect(
        "EC-1 end date before start date",
        ValidationError,
        lambda: new_request(date(2026, 11, 18), date(2026, 11, 16)),
    )
    weekend_days = working_days(date(2026, 11, 13), date(2026, 11, 16))
    check(
        "EC-2 weekends inside a range are not counted",
        weekend_days == 2,
        f"Fri 13 to Mon 16 Nov = {weekend_days} working days",
    )
    check(
        "EC-2b a weekend-only range counts zero",
        working_days(date(2026, 11, 14), date(2026, 11, 15)) == 0,
        "Sat 14 to Sun 15 Nov = 0 working days",
    )
    await expect(
        "EC-2c applying for a weekend-only range is refused",
        PolicyViolationError,
        lambda: service.apply(new_request(date(2026, 11, 14), date(2026, 11, 15))),
    )
    await expect(
        "EC-3 overlapping an approved request",
        OverlappingLeaveError,
        lambda: service.apply(new_request(date(2026, 11, 12), date(2026, 11, 17))),
    )
    await expect(
        "EC-4 insufficient balance (asks 10, has 5)",
        InsufficientBalanceError,
        lambda: service.apply(new_request(date(2026, 11, 30), date(2026, 12, 11))),
    )
    half = await service.apply(
        new_request(
            date(2026, 12, 1), date(2026, 12, 1), half_day=True, reason="School event"
        )
    )
    await service.approve(half.id, manager.id)
    check(
        "EC-5 a half day deducts 0.5",
        annual.remaining == 4.5,
        f"annual balance now {annual.remaining}",
    )
    await expect(
        "EC-5b a half day spanning two dates",
        ValidationError,
        lambda: new_request(date(2026, 12, 2), date(2026, 12, 3), half_day=True),
    )

    print("\nRULES")
    await expect(
        "Approving an already approved request",
        InvalidTransitionError,
        lambda: service.approve(trip.id, manager.id),
    )
    await expect(
        "Cancelling an approved request",
        InvalidTransitionError,
        lambda: service.cancel(trip.id, priya.id),
    )
    await expect(
        "Priya approving her own request",
        PermissionDeniedError,
        lambda: service.approve(half.id, priya.id),
    )
    await expect(
        "Reason shorter than 5 characters",
        ValidationError,
        lambda: new_request(date(2026, 12, 7), date(2026, 12, 7), reason="hi"),
    )
    await expect(
        "Annual leave starting in the past",
        PolicyViolationError,
        lambda: service.apply(new_request(date(2026, 10, 26), date(2026, 10, 27))),
    )
    await expect(
        "Casual leave longer than 2 days",
        PolicyViolationError,
        lambda: service.apply(
            new_request(
                date(2026, 12, 14), date(2026, 12, 16), leave_type=LeaveType.CASUAL
            )
        ),
    )

    passed = sum(results)
    print(f"\n{passed}/{len(results)} checks passed")
    if passed != len(results):
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
