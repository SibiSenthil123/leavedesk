"""Login accounts. An account belongs to exactly one Employee (same id)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass
class UserAccount:
    employee_id: UUID
    email: str
    password_hash: str


class InMemoryUserStore:
    def __init__(self) -> None:
        self._by_email: dict[str, UserAccount] = {}

    def add(self, account: UserAccount) -> None:
        self._by_email[account.email.lower()] = account

    def find_by_email(self, email: str) -> UserAccount | None:
        return self._by_email.get(email.strip().lower())
