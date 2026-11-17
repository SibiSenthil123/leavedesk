"""The PostgreSQL repository: the same methods as InMemoryLeaveRepository, so the
service and the API don't know or care which one they are using."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from leavedesk.db.models import (
    EmployeeRow,
    LeaveBalanceRow,
    LeaveLedgerRow,
    LeaveRequestRow,
    OutboxRow,
)
from leavedesk.domain.balance import LeaveBalance
from leavedesk.domain.exceptions import NotFoundError, OverlappingLeaveError
from leavedesk.domain.models import (
    Employee,
    LeaveRequest,
    LeaveStatus,
    LeaveType,
    NotificationEvent,
)

EXCLUSION_VIOLATION = "23P01"  # Postgres error code when an EXCLUDE constraint fires

# The session of the unit of work running right now (if any). A ContextVar is like a
# global, but each request/task gets its own value, so two requests never share one.
_current_session: ContextVar[Session | None] = ContextVar("session", default=None)


class SqlAlchemyLeaveRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    # ---- transactions ------------------------------------------------------

    @contextmanager
    def unit_of_work(self) -> Iterator[None]:
        """Everything inside runs in ONE transaction: commit at the end, rollback on error."""
        if _current_session.get() is not None:  # already inside one: join it
            yield
            return
        with self.session_factory() as session, session.begin():
            token = _current_session.set(session)
            try:
                yield
            finally:
                _current_session.reset(token)

    @contextmanager
    def _session(self) -> Iterator[Session]:
        """The unit of work's session, or a short transaction of its own."""
        current = _current_session.get()
        if current is not None:
            yield current
            return
        with self.session_factory() as session, session.begin():
            yield session

    # ---- employees ---------------------------------------------------------

    def add_employee(self, employee: Employee) -> None:
        with self._session() as s:
            s.add(
                EmployeeRow(
                    id=employee.id,
                    name=employee.name,
                    email=employee.email,
                    manager_id=employee.manager_id,
                )
            )
            s.flush()  # send the INSERT now so the next row can point to this one

    def get_employee(self, employee_id: UUID) -> Employee:
        with self._session() as s:
            row = s.get(EmployeeRow, employee_id)
            if row is None:
                raise NotFoundError(f"employee {employee_id} not found")
            return _employee(row)

    def find_employee_by_email(self, email: str) -> Employee | None:
        with self._session() as s:
            row = s.scalar(
                select(EmployeeRow).where(
                    func.lower(EmployeeRow.email) == email.strip().lower()
                )
            )
            return _employee(row) if row else None

    def all_employees(self) -> list[Employee]:
        with self._session() as s:
            rows = s.scalars(select(EmployeeRow).order_by(EmployeeRow.name))
            return [_employee(r) for r in rows]

    # ---- balances and the ledger -------------------------------------------

    def set_balance(self, balance: LeaveBalance) -> None:
        """Create a balance and write the grant into the ledger."""
        with self._session() as s:
            s.add(
                LeaveBalanceRow(
                    employee_id=balance.employee_id,
                    leave_type=balance.leave_type.value,
                    entitled=Decimal(str(balance.entitled)),
                    used=Decimal(str(balance.used)),
                )
            )
            s.add(
                LeaveLedgerRow(
                    employee_id=balance.employee_id,
                    leave_type=balance.leave_type.value,
                    days=Decimal(str(balance.entitled)),
                    note="yearly entitlement",
                )
            )
            s.flush()

    def get_balance(
        self, employee_id: UUID, leave_type: LeaveType, for_update: bool = False
    ) -> LeaveBalance:
        with self._session() as s:
            query = select(LeaveBalanceRow).where(
                LeaveBalanceRow.employee_id == employee_id,
                LeaveBalanceRow.leave_type == leave_type.value,
            )
            if for_update:
                query = query.with_for_update()  # SELECT ... FOR UPDATE
            row = s.scalar(query)
            if row is None:
                raise NotFoundError(f"no {leave_type} balance for {employee_id}")
            return LeaveBalance(
                employee_id=row.employee_id,
                leave_type=LeaveType(row.leave_type),
                entitled=float(row.entitled),
                used=float(row.used),
            )

    def record_deduction(
        self, balance: LeaveBalance, days: float, request_id: UUID
    ) -> None:
        """Save the new 'used' figure and add a minus line to the ledger."""
        with self._session() as s:
            row = s.get(
                LeaveBalanceRow, (balance.employee_id, balance.leave_type.value)
            )
            if row is None:
                raise NotFoundError(f"no {balance.leave_type} balance")
            row.used = Decimal(str(balance.used))
            s.add(
                LeaveLedgerRow(
                    employee_id=balance.employee_id,
                    leave_type=balance.leave_type.value,
                    days=-Decimal(str(days)),
                    request_id=request_id,
                    note="approved leave",
                )
            )
            s.flush()

    # ---- leave requests ----------------------------------------------------

    def add_request(self, request: LeaveRequest) -> None:
        with self._session() as s:
            s.add(
                LeaveRequestRow(
                    id=request.id,
                    employee_id=request.employee_id,
                    leave_type=request.leave_type.value,
                    start_date=request.start,
                    end_date=request.end,
                    half_day=request.half_day,
                    reason=request.reason,
                    status=request.status.value,
                    rejection_reason=request.rejection_reason,
                    created_at=request.created_at,
                )
            )
            try:
                s.flush()
            except IntegrityError as exc:
                # Two requests raced past the app's own overlap check: the database's
                # EXCLUDE constraint caught it. Report it as the usual domain error.
                if getattr(exc.orig, "sqlstate", None) == EXCLUSION_VIOLATION:
                    raise OverlappingLeaveError("(found by the database)") from None
                raise

    def get_request(self, request_id: UUID, for_update: bool = False) -> LeaveRequest:
        with self._session() as s:
            query = select(LeaveRequestRow).where(LeaveRequestRow.id == request_id)
            if for_update:
                query = query.with_for_update()
            row = s.scalar(query)
            if row is None:
                raise NotFoundError(f"leave request {request_id} not found")
            return _request(row)

    def save_request(self, request: LeaveRequest) -> None:
        """Write back the fields that can change: status and rejection reason."""
        with self._session() as s:
            row = s.get(LeaveRequestRow, request.id)
            if row is None:
                raise NotFoundError(f"leave request {request.id} not found")
            row.status = request.status.value
            row.rejection_reason = request.rejection_reason
            s.flush()

    def requests_for(self, employee_id: UUID) -> list[LeaveRequest]:
        with self._session() as s:
            rows = s.scalars(
                select(LeaveRequestRow).where(
                    LeaveRequestRow.employee_id == employee_id
                )
            )
            return [_request(r) for r in rows]

    # ---- outbox ------------------------------------------------------------

    def add_outbox(self, event: NotificationEvent, request_id: UUID) -> None:
        with self._session() as s:
            s.add(OutboxRow(event=event.value, request_id=request_id))
            s.flush()


def _employee(row: EmployeeRow) -> Employee:
    return Employee(
        id=row.id, name=row.name, email=row.email, manager_id=row.manager_id
    )


def _request(row: LeaveRequestRow) -> LeaveRequest:
    return LeaveRequest(
        id=row.id,
        employee_id=row.employee_id,
        leave_type=LeaveType(row.leave_type),
        start=row.start_date,
        end=row.end_date,
        half_day=row.half_day,
        reason=row.reason,
        status=LeaveStatus(row.status),
        rejection_reason=row.rejection_reason,
        created_at=row.created_at,
    )
