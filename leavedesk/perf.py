"""Performance lab for PERF.md.

python -m leavedesk.perf seed      # adds 20,000 employees and 100,000 leave requests
python -m leavedesk.perf explain   # runs the 3 queries with EXPLAIN (ANALYZE, BUFFERS)

Use a separate database for this (see PERF.md), not the one you demo the API with."""

from __future__ import annotations

import argparse
import time

from sqlalchemy import Connection, text

from leavedesk.api.config import DatabaseSettings
from leavedesk.db.engine import make_engine

# Everything is generated inside PostgreSQL with generate_series: much faster than
# sending 100,000 INSERTs from Python. Each employee gets 5 requests, 3 weeks apart,
# so none overlap (the EXCLUDE constraint would refuse them).
SEED_SQL = [
    # 2,000 managers, each managing 9 people -> 20,000 employees in total
    """INSERT INTO employees (id, name, email, manager_id)
       SELECT gen_random_uuid(),
              (ARRAY['Asha','Ravi','Divya','Karthik','Lakshmi','Vikram','Anita','Suresh'])[1 + g % 8]
                || ' ' || (ARRAY['Menon','Pillai','Reddy','Sharma','Iyer','Khan','Das','Gupta'])[1 + (g / 8) % 8]
                || ' ' || g,
              'perf' || g || '@leavedesk.dev',
              NULL
       FROM generate_series(1, 2000) AS g""",
    """INSERT INTO employees (id, name, email, manager_id)
       SELECT gen_random_uuid(),
              (ARRAY['Meena','Arun','Pooja','Naveen','Sneha','Rahul','Kavya','Ajay'])[1 + g % 8]
                || ' ' || (ARRAY['Nair','Rao','Joshi','Patel','Bose','Singh','Varma','Shetty'])[1 + (g / 8) % 8]
                || ' ' || g,
              'perf-staff' || g || '@leavedesk.dev',
              (SELECT id FROM employees WHERE lower(email) = 'perf' || (1 + g % 2000) || '@leavedesk.dev')
       FROM generate_series(1, 18000) AS g""",
    """INSERT INTO leave_requests
           (id, employee_id, leave_type, start_date, end_date, reason, status, created_at)
       SELECT gen_random_uuid(), e.id,
              (ARRAY['ANNUAL','SICK','CASUAL'])[1 + k % 3],
              DATE '2025-01-06' + (k * 21),
              DATE '2025-01-06' + (k * 21) + 2,
              'Generated for PERF.md',
              CASE WHEN random() < 0.05 THEN 'PENDING'
                   WHEN random() < 0.85 THEN 'APPROVED'
                   ELSE 'REJECTED' END,
              now() - (k * 21 || ' days')::interval - (random() * interval '1 day')
       FROM employees e
       CROSS JOIN generate_series(0, 4) AS k
       WHERE e.email LIKE 'perf%'""",
    "ANALYZE",  # refresh the planner's statistics after a big load
]

# The three questions the app asks most. :params are bound, never pasted into the SQL.
QUERIES = {
    "1. Manager's pending queue": (
        """SELECT r.id, r.start_date, r.end_date, e.name
           FROM leave_requests r JOIN employees e ON e.id = r.employee_id
           WHERE e.manager_id = (SELECT id FROM employees WHERE lower(email) = 'perf7@leavedesk.dev')
             AND r.status = 'PENDING'
           ORDER BY r.created_at
           LIMIT 20""",
        {},
    ),
    "2. Employee history (newest first)": (
        """SELECT id, leave_type, start_date, end_date, status
           FROM leave_requests
           WHERE employee_id = (SELECT id FROM employees WHERE lower(email) = 'perf-staff42@leavedesk.dev')
           ORDER BY start_date DESC
           LIMIT 20""",
        {},
    ),
    "3. Name search": (
        "SELECT id, name FROM employees WHERE name ILIKE :pattern LIMIT 20",
        {"pattern": "%varma 1777%"},
    ),
}


def seed(conn: Connection) -> None:
    for statement in SEED_SQL:
        started = time.perf_counter()
        conn.execute(text(statement))
        print(f"  {statement.split()[0]:<7} {time.perf_counter() - started:5.1f} s")
    count = conn.scalar(text("SELECT count(*) FROM leave_requests"))
    print(f"leave_requests now has {count:,} rows")


def explain(conn: Connection) -> None:
    for title, (query, params) in QUERIES.items():
        rows = conn.execute(text("EXPLAIN (ANALYZE, BUFFERS) " + query), params)
        plan = [r[0] for r in rows]
        scans = [line.strip() for line in plan if "Scan" in line]
        total = next(line for line in plan if line.startswith("Execution Time"))
        print(f"\n{title}\n  {total}")
        for scan in scans:
            print(f"  {scan.split('  (')[0]}")


def main() -> None:
    parser = argparse.ArgumentParser(description="LeaveDesk performance lab")
    parser.add_argument("action", choices=["seed", "explain", "plan"])
    args = parser.parse_args()
    engine = make_engine(DatabaseSettings(statement_timeout_ms=120_000))
    with engine.begin() as conn:
        if args.action == "seed":
            seed(conn)
        elif args.action == "explain":
            explain(conn)
        else:  # "plan": the full EXPLAIN output, to paste into PERF.md
            for title, (query, params) in QUERIES.items():
                print(f"\n-- {title}")
                for row in conn.execute(
                    text("EXPLAIN (ANALYZE, BUFFERS) " + query), params
                ):
                    print(row[0])
    engine.dispose()


if __name__ == "__main__":
    main()
