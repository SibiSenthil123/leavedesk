"""Demo people so the API is usable straight away. Turn off with LEAVEDESK_SEED_DEMO_DATA=false."""

from __future__ import annotations

from leavedesk.api.container import Container
from leavedesk.api.security import hash_password
from leavedesk.api.users import UserAccount
from leavedesk.domain.balance import LeaveBalance
from leavedesk.domain.models import Employee, LeaveType

ENTITLEMENTS = {LeaveType.ANNUAL: 18, LeaveType.SICK: 10, LeaveType.CASUAL: 6}


def seed_demo_data(container: Container, password: str) -> dict[str, Employee]:
    """Meera manages Arjun; Arjun manages Priya and Kiran. All share the demo password."""
    meera = Employee(name="Meera Iyer", email="meera@leavedesk.dev")
    arjun = Employee(name="Arjun Rao", email="arjun@leavedesk.dev", manager_id=meera.id)
    priya = Employee(
        name="Priya Nair", email="priya@leavedesk.dev", manager_id=arjun.id
    )
    kiran = Employee(name="Kiran Das", email="kiran@leavedesk.dev", manager_id=arjun.id)
    people = {"meera": meera, "arjun": arjun, "priya": priya, "kiran": kiran}

    password_hash = hash_password(password)  # hashed once: Argon2 is slow on purpose
    for person in people.values():
        container.repo.add_employee(person)
        container.users.add(UserAccount(person.id, person.email, password_hash))
        for leave_type, days in ENTITLEMENTS.items():
            container.repo.set_balance(LeaveBalance(person.id, leave_type, days))
    return people
