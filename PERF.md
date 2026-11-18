# LeaveDesk: query performance (Capstone 3)

Three queries the app runs most, measured on **100,000 leave requests and 20,000 employees**, before and after migration `0002_perf_indexes`. Numbers are from one run with `EXPLAIN (ANALYZE, BUFFERS)` on PostgreSQL 16; yours will differ a little, but the plan shapes should match.

| Query | Before (0001) | After (0002) | Index added |
| --- | --- | --- | --- |
| 1. Manager's pending queue | 1.2 ms, bitmap scan on the EXCLUDE index, then filters out non-pending rows | 0.26 ms, Index Scan on `ix_requests_pending_by_employee` | partial: `(employee_id, created_at) WHERE status = 'PENDING'` |
| 2. Employee history, newest first | 13.3 ms, **Seq Scan** on `leave_requests` (99,995 rows removed by filter) | 0.09 ms, Bitmap Index Scan on `ix_requests_employee_start` | composite: `(employee_id, start_date DESC)` |
| 3. Name search `ILIKE '%varma 1777%'` | 10 to 18 ms, **Seq Scan** on `employees` | 0.2 ms, Bitmap Index Scan on `ix_employees_name_trgm` | GIN trigram (`pg_trgm`) on `name` |

## What each result means

1. **Partial index.** Only about 5% of requests are PENDING, so an index of just those rows is small and is exactly what a manager's queue reads. Even before 0002 this query was not a full scan: the GiST index behind the overlap EXCLUDE constraint starts with `employee_id`, so Postgres used it. That is a nice side effect of the constraint, but it still read every status and threw most away.
2. **Composite index, and the missing foreign-key index.** Postgres does not index foreign keys by itself. Without an index on `employee_id`, finding one person's 5 requests means reading all 100,000 rows (1,543 buffer pages). The composite index starts with `employee_id`, so it also serves as the foreign key's index.
3. **Trigram index.** A normal B-tree index can't help `'%text%'` because the text can start anywhere. `pg_trgm` splits names into 3-letter pieces and indexes those.

## How to reproduce

Use a separate database so the demo data stays clean:

```bash
docker compose exec db createdb -U leavedesk leavedesk_perf
export LEAVEDESK_DATABASE_URL=postgresql+psycopg://leavedesk:leavedesk-dev-only@localhost:5433/leavedesk_perf
alembic upgrade 0001             # tables, but no performance indexes yet
python -m leavedesk.perf seed     # 20k employees, 100k requests (a few seconds)
python -m leavedesk.perf explain  # BEFORE: note the Seq Scans and times
alembic upgrade head              # adds the 3 indexes
python -m leavedesk.perf explain  # AFTER: Index Scans, much faster
unset LEAVEDESK_DATABASE_URL      # back to the normal database
```

`python -m leavedesk.perf plan` prints the full plans if you want to paste them here.

## Not measured (stretch)

Keyset pagination (`WHERE (created_at, id) < (:last_created, :last_id)`) instead of `OFFSET`: deep `OFFSET` pages read and throw away every earlier row, while keyset jumps straight to the next page using an index.
