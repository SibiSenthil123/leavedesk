# LeaveDesk

Employee leave management, grown over the workshop:

- **Capstone 1:** the domain rules in plain Python ([SPEC.md](SPEC.md)). Run `python -m leavedesk.demo`.
- **Capstone 2:** a FastAPI REST API with login, notifications, tests and Docker ([API_SPEC.md](API_SPEC.md)).
- **Capstone 3:** PostgreSQL storage with SQLAlchemy 2 and Alembic, database constraints, row locking, an email outbox and measured indexes ([SCHEMA.md](SCHEMA.md), [PERF.md](PERF.md)).

## Setup (Mac)

Requires Python 3.12 or newer.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
```

Then open `.env` and replace `LEAVEDESK_JWT_SECRET` with your own value from
`python3 -c "import secrets; print(secrets.token_urlsafe(48))"`.

## Start the database (once per session)

Docker Desktop must be running.

```bash
docker compose up -d db                                     # PostgreSQL in the background
docker compose exec db createdb -U leavedesk leavedesk_test # first time only: database for pytest
alembic upgrade head                                        # build or update the tables
```

## Run the API

```bash
uvicorn leavedesk.api.main:create_app --factory --reload
```

Emails wait in the `notification_outbox` table. Send them with `python -m leavedesk.worker` (keeps running) or `python -m leavedesk.worker --once`.

Look inside the database: `docker compose exec db psql -U leavedesk -d leavedesk` (`\dt` lists tables, `\q` quits).

Open http://127.0.0.1:8000/docs, click **Authorize**, and log in as `priya@leavedesk.dev` (employee) or `arjun@leavedesk.dev` (Priya's manager) with the `LEAVEDESK_DEMO_PASSWORD` from `.env`.

## Test and lint

The tests use the `leavedesk_test` database and empty it before each test.

```bash
pytest
ruff check .
ruff format --check .
```

## Run with Docker

```bash
docker compose up --build
```

This starts the database, the API (it runs `alembic upgrade head` first) and the outbox worker. The API is on http://localhost:8000/docs. Stop with Ctrl+C, then `docker compose down`. `docker compose down -v` also deletes the database's data.

## Layout

```text
leavedesk/
├── demo.py                  # Capstone 1 walkthrough (15 checks)
├── worker.py                # outbox worker: sends the waiting emails
├── perf.py                  # PERF.md lab: seed 100k requests, EXPLAIN the queries
├── domain/                  # business rules, no web framework
├── db/                      # PostgreSQL: engine, table models, repository
└── api/
    ├── main.py              # create_app(): wires everything together
    ├── config.py            # Settings from environment / .env
    ├── security.py          # Argon2id passwords, JWT create/decode
    ├── users.py             # login accounts (in memory)
    ├── container.py         # builds repo, service, notifiers once
    ├── seed.py              # demo people and balances
    ├── deps.py              # FastAPI dependencies: current user, service
    ├── schemas.py           # request/response models, error shape
    ├── errors.py            # domain error -> HTTP status + JSON error
    ├── middleware.py        # X-Request-ID and one log line per request
    └── routers/             # auth, employees, leave_requests, notifications
alembic/versions/            # 0001 tables and constraints, 0002 performance indexes
tests/                       # pytest: 40 tests on PostgreSQL incl. failure paths
```
