# LeaveDesk: Capstone 3 specification (PostgreSQL)

Capstone 3 moves LeaveDesk's data from memory into PostgreSQL. Every rule in [SPEC.md](SPEC.md) and every endpoint in [API_SPEC.md](API_SPEC.md) stays the same: the 33 Day 2 tests must pass unchanged. What changes is **where data lives** and **what the database guarantees by itself**.

## 1. Stack

- PostgreSQL 17 (in Docker), SQLAlchemy 2.0 with `Mapped[]` models, psycopg 3 driver.
- Alembic migrations build the tables. Nobody creates tables by hand or with `create_all()`.
- The domain keeps its own Pydantic models. `leavedesk/db/repository.py` translates rows to domain objects, so the service never sees SQLAlchemy.

## 2. Tables

| Table | Key | Purpose |
| --- | --- | --- |
| `employees` | `id` uuid | People. `manager_id` points to another employee. |
| `leave_balances` | (`employee_id`, `leave_type`) | Entitled and used days per person per leave type. |
| `leave_requests` | `id` uuid | Every request with its status. |
| `leave_ledger` | `id` bigint identity | Append-only: +18 when days are granted, -5 when leave is approved. |
| `notification_outbox` | `id` bigint identity | Messages to email, written in the same transaction as the change. |

## 3. Design decisions

| Decision | Choice | Why |
| --- | --- | --- |
| Primary keys | uuid for people and requests; bigint identity for ledger and outbox | The app makes uuids before saving (Day 1 code); ledger and outbox rows are only made by the database and are read in order. |
| Leave type and status | `varchar` + `CHECK (... IN (...))` | A fixed, short list that matches the Python enums. A lookup table is for lists users edit; a Postgres ENUM is hard to change later. |
| Days | `numeric(5,1)` | Exact decimals: 0.5 + 0.5 is exactly 1.0. Floats can drift. Never use float for money or days. |
| Times | `timestamptz` | Stored in UTC, shown in any time zone, never ambiguous. |
| Email | unique index on `lower(email)` | `Priya@...` and `priya@...` are the same person. |
| Foreign keys | indexed | Postgres does not index foreign keys automatically. `leave_requests.employee_id` is left unindexed in migration 0001 on purpose, so PERF.md can measure the difference; 0002 adds an index that starts with it. |
| Balance | `leave_balances.used` plus `leave_ledger` | The balance row is fast to read and lock; the ledger is the history, and its sum must equal `remaining`. |

## 4. Constraints the database enforces

- `NOT NULL` on every required column.
- `CHECK (end_date >= start_date)`, `CHECK (NOT half_day OR start_date = end_date)`, `CHECK (used >= 0 AND used <= entitled)`.
- **No overlapping leave:** `EXCLUDE USING gist (employee_id WITH =, daterange(start_date, end_date, '[]') WITH &&) WHERE (status IN ('PENDING','APPROVED'))`. Needs the `btree_gist` extension. If two requests race past the app's own check, the database refuses the second one and the API still answers 409.

## 5. Transactions and locking

- Each use case (apply, approve, reject, cancel) runs in **one transaction** (`repo.unit_of_work()`): everything is saved or nothing is.
- Approve locks the request and the balance with `SELECT ... FOR UPDATE`. A second manager approving at the same moment waits, then sees APPROVED and gets 409. Days are deducted once.
- Every connection sets `statement_timeout` (5 s) and `lock_timeout` (3 s), so nothing hangs forever.
- Raw SQL only through `text()` with bound `:params`, never string formatting.

## 6. Notifications through the outbox

- In-app notifications still go out as Day 2 `BackgroundTasks` (fast, live over SSE).
- Email goes through `notification_outbox`: the row is written in the same transaction as the change. `python -m leavedesk.worker` picks up rows with `FOR UPDATE SKIP LOCKED`, sends them, and marks them processed. If the change rolls back, there is no row, so no email.

## 7. Acceptance criteria

- DB-1 `alembic upgrade head` builds every table on an empty database; `alembic downgrade 0001` works.
- DB-2 The 33 Day 2 tests pass unchanged on PostgreSQL.
- DB-3 A request survives an app restart.
- DB-4 An overlapping PENDING/APPROVED request inserted with plain SQL is refused by `ex_request_no_overlap`.
- DB-5 A row with end before start is refused by `ck_request_dates`.
- DB-6 Two approvals of the same request at the same moment: one succeeds, one gets 409, the ledger has one deduction.
- DB-7 The ledger sum equals the remaining balance after an approval.
- DB-8 If an approval fails after its outbox row was written, nothing is saved: no outbox row, no deduction, still PENDING.
- DB-9 The worker sends each outbox message once.
- DB-10 PERF.md shows each of the three main queries leaving its sequential scan after migration 0002.

## 8. Task plan (one PR each)

| PR | Task | Files |
| --- | --- | --- |
| 1 | This spec | `SCHEMA.md` |
| 2 | Database foundation: settings, engine, models, first migration | `requirements*.txt`, `pyproject.toml`, `.env.example`, `api/config.py`, `db/__init__.py`, `db/engine.py`, `db/models.py`, `alembic.ini`, `alembic/env.py`, `alembic/script.py.mako`, `alembic/versions/0001_initial_schema.py` |
| 3 | PostgreSQL repository and transactions | `domain/repository.py`, `domain/service.py`, `db/repository.py`, `api/container.py`, `api/seed.py`, `tests/conftest.py` |
| 4 | Outbox worker and the database tests | `worker.py`, `tests/test_postgres.py` |
| 5 | Indexes and PERF.md | `alembic/versions/0002_perf_indexes.py`, `perf.py`, `PERF.md` |
| 6 | Docker, README and AI notes | `Dockerfile`, `docker-compose.yml`, `README.md`, `AI_NOTES_CAPSTONE3.md` |

Not in this capstone (stretch): `tenant_id` and row-level security, users and login lockout in the database, `Idempotency-Key`, a `version` column, `LISTEN/NOTIFY` for SSE, keyset pagination.
