"""Indexes for the three slow queries measured in PERF.md.

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Employee history: "my requests, newest first" -> composite index.
    #    It starts with employee_id, so it also serves as the foreign key's index.
    op.create_index(
        "ix_requests_employee_start",
        "leave_requests",
        ["employee_id", sa.text("start_date DESC")],
    )
    # 2. Manager's queue: only PENDING rows matter -> partial index (small and fast).
    op.create_index(
        "ix_requests_pending_by_employee",
        "leave_requests",
        ["employee_id", "created_at"],
        postgresql_where=sa.text("status = 'PENDING'"),
    )
    # 3. Name search with ILIKE '%text%' -> trigram index (a normal index can't help).
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_index(
        "ix_employees_name_trgm",
        "employees",
        ["name"],
        postgresql_using="gin",
        postgresql_ops={"name": "gin_trgm_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_employees_name_trgm", table_name="employees")
    op.drop_index("ix_requests_pending_by_employee", table_name="leave_requests")
    op.drop_index("ix_requests_employee_start", table_name="leave_requests")
