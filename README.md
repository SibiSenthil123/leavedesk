# LeaveDesk

Employee leave management, grown over the workshop:

- **Capstone 1:** the domain rules in plain Python ([SPEC.md](SPEC.md)). Run `python -m leavedesk.demo`.
- **Capstone 2:** a FastAPI REST API with login, notifications, tests and Docker ([API_SPEC.md](API_SPEC.md)).

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

## Run the API

```bash
uvicorn leavedesk.api.main:create_app --factory --reload
```

Open http://127.0.0.1:8000/docs, click **Authorize**, and log in as `priya@leavedesk.dev` (employee) or `arjun@leavedesk.dev` (Priya's manager) with the `LEAVEDESK_DEMO_PASSWORD` from `.env`.

## Test and lint

```bash
pytest
ruff check .
ruff format --check .
```

## Run with Docker

```bash
docker compose up --build
```

The API is on http://localhost:8000/docs. The `db` service (PostgreSQL) starts too but isn't used until Day 3. Stop with Ctrl+C, then `docker compose down`.

## Layout

```text
leavedesk/
├── demo.py                  # Capstone 1 walkthrough (15 checks)
├── domain/                  # business rules, no web framework
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
tests/                       # pytest: 33 tests incl. failure paths
```
