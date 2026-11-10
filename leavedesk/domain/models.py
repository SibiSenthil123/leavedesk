"""Pydantic models: data that will arrive as JSON from the Day 2 API, so it is validated."""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


class LeaveType(StrEnum):
    ANNUAL = "ANNUAL"
    SICK = "SICK"
    CASUAL = "CASUAL"


class LeaveStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class NotificationEvent(StrEnum):
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class Employee(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    manager_id: UUID | None = None  # None = top of the tree (no manager)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return value.strip()


class LeaveRequest(BaseModel):
    # validate_assignment=True re-runs validation when a field is changed later,
    # so `request.status = "BOGUS"` fails instead of silently storing bad data.
    model_config = {"validate_assignment": True}

    id: UUID = Field(default_factory=uuid4)
    employee_id: UUID
    leave_type: LeaveType
    start: date
    end: date
    half_day: bool = False
    reason: str = Field(min_length=5, max_length=500)
    status: LeaveStatus = LeaveStatus.PENDING
    rejection_reason: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("reason")
    @classmethod
    def strip_reason(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def check_dates(self) -> LeaveRequest:
        if self.end < self.start:
            raise ValueError("end date must be on or after start date")
        if self.half_day and self.start != self.end:
            raise ValueError("a half-day request must start and end on the same date")
        return self


class Notification(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    recipient_id: UUID
    event: NotificationEvent
    request_id: UUID
    message: str
    read: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
