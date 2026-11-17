"""Initial schema: employees, balances, leave requests, ledger, outbox.

Revision ID: 0001
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TZ = sa.DateTime(timezone=True)  # timestamptz
DAYS = sa.Numeric(5, 1)  # exact: 0.5 + 0.5 == 1.0
LEAVE_TYPES = "('ANNUAL', 'SICK', 'CASUAL')"


def upgrade() -> None:
    # btree_gist lets one EXCLUDE constraint mix "=" on a uuid with "&&" on a range.
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    op.create_table(
        "employees",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("manager_id", sa.Uuid(), sa.ForeignKey("employees.id")),
        sa.Column("created_at", TZ, server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "uq_employees_email", "employees", [sa.text("lower(email)")], unique=True
    )
    op.create_index("ix_employees_manager_id", "employees", ["manager_id"])

    op.create_table(
        "leave_balances",
        sa.Column(
            "employee_id", sa.Uuid(), sa.ForeignKey("employees.id"), primary_key=True
        ),
        sa.Column("leave_type", sa.String(10), primary_key=True),
        sa.Column("entitled", DAYS, nullable=False),
        sa.Column("used", DAYS, server_default="0", nullable=False),
        sa.CheckConstraint(f"leave_type IN {LEAVE_TYPES}", name="ck_balance_type"),
        sa.CheckConstraint("used >= 0 AND used <= entitled", name="ck_balance_used"),
    )

    op.create_table(
        "leave_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "employee_id", sa.Uuid(), sa.ForeignKey("employees.id"), nullable=False
        ),
        sa.Column("leave_type", sa.String(10), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("half_day", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("rejection_reason", sa.String(500)),
        sa.Column("created_at", TZ, nullable=False),
        sa.CheckConstraint("end_date >= start_date", name="ck_request_dates"),
        sa.CheckConstraint(
            "NOT half_day OR start_date = end_date", name="ck_request_half_day"
        ),
        sa.CheckConstraint(f"leave_type IN {LEAVE_TYPES}", name="ck_request_type"),
        sa.CheckConstraint(
            "status IN ('PENDING', 'APPROVED', 'REJECTED', 'CANCELLED')",
            name="ck_request_status",
        ),
        # No two PENDING/APPROVED requests of one employee may overlap.
        postgresql.ExcludeConstraint(
            ("employee_id", "="),
            (sa.text("daterange(start_date, end_date, '[]')"), "&&"),
            where=sa.text("status IN ('PENDING', 'APPROVED')"),
            using="gist",
            name="ex_request_no_overlap",
        ),
    )
    # leave_requests.employee_id is NOT indexed yet, on purpose: PERF.md measures the
    # queries without it first. Migration 0002 adds an index that starts with it.

    op.create_table(
        "leave_ledger",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "employee_id", sa.Uuid(), sa.ForeignKey("employees.id"), nullable=False
        ),
        sa.Column("leave_type", sa.String(10), nullable=False),
        sa.Column("days", DAYS, nullable=False),
        sa.Column("request_id", sa.Uuid(), sa.ForeignKey("leave_requests.id")),
        sa.Column("note", sa.String(100), nullable=False),
        sa.Column("created_at", TZ, server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_leave_ledger_employee_type", "leave_ledger", ["employee_id", "leave_type"]
    )
    op.create_index("ix_leave_ledger_request_id", "leave_ledger", ["request_id"])

    op.create_table(
        "notification_outbox",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("event", sa.String(20), nullable=False),
        sa.Column(
            "request_id", sa.Uuid(), sa.ForeignKey("leave_requests.id"), nullable=False
        ),
        sa.Column("created_at", TZ, server_default=sa.func.now(), nullable=False),
        sa.Column("processed_at", TZ),
    )
    op.create_index(
        "ix_outbox_unprocessed",
        "notification_outbox",
        ["id"],
        postgresql_where=sa.text("processed_at IS NULL"),
    )
    op.create_index("ix_outbox_request_id", "notification_outbox", ["request_id"])


def downgrade() -> None:
    for table in (
        "notification_outbox",
        "leave_ledger",
        "leave_requests",
        "leave_balances",
        "employees",
    ):
        op.drop_table(table)
