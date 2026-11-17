"""Tables as SQLAlchemy 2 classes. These are the DATABASE shapes; the domain keeps its
own Pydantic models, and the repository translates between the two."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

LEAVE_TYPES = "('ANNUAL', 'SICK', 'CASUAL')"
STATUSES = "('PENDING', 'APPROVED', 'REJECTED', 'CANCELLED')"


class Base(DeclarativeBase):
    # Every datetime column becomes timestamptz: stored in UTC, never ambiguous.
    type_annotation_map = {datetime: DateTime(timezone=True)}


class EmployeeRow(Base):
    __tablename__ = "employees"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(254))
    # Postgres does NOT index foreign keys by itself, so we add the index.
    manager_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("employees.id"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    __table_args__ = (
        # lower(email) so Priya@... and priya@... count as the same address
        Index("uq_employees_email", func.lower(email), unique=True),
        # Trigram index for name search with ILIKE '%text%' (migration 0002)
        Index(
            "ix_employees_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
    )


class LeaveBalanceRow(Base):
    __tablename__ = "leave_balances"

    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("employees.id"), primary_key=True
    )
    leave_type: Mapped[str] = mapped_column(String(10), primary_key=True)
    # numeric(5,1): exact decimals, so 0.5 + 0.5 is exactly 1.0 (a float may not be)
    entitled: Mapped[Decimal] = mapped_column(Numeric(5, 1))
    used: Mapped[Decimal] = mapped_column(Numeric(5, 1), server_default="0")

    __table_args__ = (
        CheckConstraint(f"leave_type IN {LEAVE_TYPES}", name="ck_balance_type"),
        CheckConstraint("used >= 0 AND used <= entitled", name="ck_balance_used"),
    )


class LeaveRequestRow(Base):
    __tablename__ = "leave_requests"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    employee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employees.id"))
    leave_type: Mapped[str] = mapped_column(String(10))
    start_date: Mapped[date]
    end_date: Mapped[date]
    half_day: Mapped[bool] = mapped_column(server_default=text("false"))
    reason: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(10))
    rejection_reason: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime]

    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="ck_request_dates"),
        CheckConstraint(
            "NOT half_day OR start_date = end_date", name="ck_request_half_day"
        ),
        CheckConstraint(f"leave_type IN {LEAVE_TYPES}", name="ck_request_type"),
        CheckConstraint(f"status IN {STATUSES}", name="ck_request_status"),
        # The database itself refuses two PENDING/APPROVED requests of the same
        # employee whose date ranges overlap (&&), even if the app forgot to check.
        ExcludeConstraint(
            ("employee_id", "="),
            (text("daterange(start_date, end_date, '[]')"), "&&"),
            where=text("status IN ('PENDING', 'APPROVED')"),
            using="gist",
            name="ex_request_no_overlap",
        ),
        # Indexes from migration 0002 (see PERF.md for why each one exists)
        Index("ix_requests_employee_start", "employee_id", text("start_date DESC")),
        Index(
            "ix_requests_pending_by_employee",
            "employee_id",
            "created_at",
            postgresql_where=text("status = 'PENDING'"),
        ),
    )


class LeaveLedgerRow(Base):
    """Append-only: rows are only ever added. The balance is the sum of the movements."""

    __tablename__ = "leave_ledger"

    id: Mapped[int] = mapped_column(primary_key=True)  # bigint identity
    employee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employees.id"))
    leave_type: Mapped[str] = mapped_column(String(10))
    days: Mapped[Decimal] = mapped_column(Numeric(5, 1))  # +18 grant, -5 approved leave
    request_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("leave_requests.id"), index=True
    )
    note: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    __table_args__ = (
        Index("ix_leave_ledger_employee_type", "employee_id", "leave_type"),
    )


class OutboxRow(Base):
    """Messages to send, written in the SAME transaction as the change they describe."""

    __tablename__ = "notification_outbox"

    id: Mapped[int] = mapped_column(primary_key=True)
    event: Mapped[str] = mapped_column(String(20))
    request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("leave_requests.id"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    processed_at: Mapped[datetime | None]

    __table_args__ = (
        # Partial index: only the unsent rows, which is all the worker ever looks for.
        Index(
            "ix_outbox_unprocessed",
            "id",
            postgresql_where=text("processed_at IS NULL"),
        ),
    )
