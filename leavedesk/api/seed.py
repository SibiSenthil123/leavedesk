"""Demo people so the API is usable straight away. Turn off with LEAVEDESK_SEED_DEMO_DATA=false."""

from __future__ import annotations

from leavedesk.api.container import Container
from leavedesk.api.security import hash_password
from leavedesk.api.users import UserAccount
from leavedesk.domain.balance import LeaveBalance
from leavedesk.domain.models import Employee, LeaveType

ENTITLEMENTS = {LeaveType.ANNUAL: 18, LeaveType.SICK: 10, LeaveType.CASUAL: 6}

# (key, full name, key of their manager). Managers come before their reports.
DEMO_PEOPLE = [
    ("meera", "Meera Iyer", None),
    ("arjun", "Arjun Rao", "meera"),
    ("priya", "Priya Nair", "arjun"),
    ("kiran", "Kiran Das", "arjun"),
]


def seed_demo_data(container: Container, password: str) -> dict[str, Employee]:
    """Meera manages Arjun; Arjun manages Priya and Kiran. All share the demo password.

    Safe to run on every start: people already in the database are kept as they are."""
    people: dict[str, Employee] = {}
    with container.repo.unit_of_work():  # all four people, or none
        for key, name, manager_key in DEMO_PEOPLE:
            email = f"{key}@leavedesk.dev"
            existing = container.repo.find_employee_by_email(email)
            if existing is not None:  # saved on an earlier start
                people[key] = existing
                continue
            manager_id = people[manager_key].id if manager_key else None
            person = Employee(name=name, email=email, manager_id=manager_id)
            container.repo.add_employee(person)
            for leave_type, days in ENTITLEMENTS.items():
                container.repo.set_balance(LeaveBalance(person.id, leave_type, days))
            people[key] = person

    # Login accounts still live in memory, so they are rebuilt on every start.
    password_hash = hash_password(password)  # hashed once: Argon2 is slow on purpose
    for person in people.values():
        container.users.add(UserAccount(person.id, person.email, password_hash))
    return people
