"""Request and response shapes. Kept apart from the domain models so the API
contract can't change by accident when the domain does."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Generic, Literal, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from leavedesk.domain.models import LeaveStatus, LeaveType, NotificationEvent

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str | None = None
    details: list[dict[str, Any]] | None = None


class ErrorResponse(BaseModel):
    """The single error shape for every 4xx and 5xx."""

    error: ErrorDetail


# ---- auth ----------------------------------------------------------------


class Token(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 (not a password)
    expires_in: int  # seconds


class Me(BaseModel):
    id: UUID
    name: str
    email: str
    manager_id: UUID | None
    is_manager: bool


# ---- employees -----------------------------------------------------------


class BalanceOut(BaseModel):
    leave_type: LeaveType
    entitled: float
    used: float
    remaining: float


# ---- leave requests ------------------------------------------------------


class LeaveRequestCreate(BaseModel):
    """What a client sends. employee_id is NOT here: it comes from the token."""

    model_config = ConfigDict(extra="forbid")

    leave_type: LeaveType
    start: date
    end: date
    half_day: bool = False
    reason: str = Field(min_length=5, max_length=500)

    @field_validator("reason")
    @classmethod
    def strip_reason(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 5:
            raise ValueError("reason must be at least 5 characters")
        return value

    @model_validator(mode="after")
    def check_dates(self) -> LeaveRequestCreate:
        if self.end < self.start:
            raise ValueError("end date must be on or after start date")
        if self.half_day and self.start != self.end:
            raise ValueError("a half-day request must start and end on the same date")
        return self


class RejectBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=5, max_length=500)

    @field_validator("reason")
    @classmethod
    def strip_reason(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 5:
            raise ValueError("reason must be at least 5 characters")
        return value


class LeaveRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    leave_type: LeaveType
    start: date
    end: date
    half_day: bool
    reason: str
    status: LeaveStatus
    rejection_reason: str | None
    created_at: datetime


LeaveSort = Literal["created_at", "-created_at", "start", "-start"]


# ---- notifications -------------------------------------------------------


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event: NotificationEvent
    request_id: UUID
    message: str
    read: bool
    created_at: datetime


class ReadAllResult(BaseModel):
    marked_read: int
