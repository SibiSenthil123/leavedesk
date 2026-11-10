# LeaveDesk: Capstone 2 API specification

Capstone 2 puts a REST API in front of the Capstone 1 domain (see [SPEC.md](SPEC.md)). Every business rule from Capstone 1 still applies; this spec only adds HTTP, login and notifications. Storage stays in memory behind the `LeaveRepository` interface; Day 3 swaps in PostgreSQL.

## 1. Users and roles

- Every user is an Employee and logs in with email and password.
- A **manager** is any employee that someone else's `manager_id` points to. There is no separate role table.
- Passwords are stored only as Argon2id hashes. Login failures always say "invalid email or password", whether the email exists or not.
- A login returns a JWT (HS256, 30 minutes). Every other endpoint except `/health` needs `Authorization: Bearer <token>`.

Demo data (when `LEAVEDESK_SEED_DEMO_DATA=true`): Meera manages Arjun; Arjun manages Priya and Kiran. Each gets 18 annual, 10 sick and 6 casual days.

## 2. Endpoints

| Method | Path | Who | Request | Success | Errors |
| --- | --- | --- | --- | --- | --- |
| POST | `/auth/login` | anyone | form: `username` (email), `password` | 200 `Token` | 401, 422 |
| GET | `/auth/me` | logged in | | 200 `Me` | 401 |
| GET | `/employees/{id}/balance` | self, or their manager | | 200 `BalanceOut[]` | 401, 403, 404 |
| POST | `/leave-requests` | logged in (applies for self) | `LeaveRequestCreate` | 201 `LeaveRequestOut` | 401, 409 overlap, 422 invalid dates / balance / policy |
| GET | `/leave-requests` | logged in | query: `status`, `employee_id`, `sort`, `limit`, `offset` | 200 `Page[LeaveRequestOut]` | 401, 422 |
| GET | `/leave-requests/{id}` | owner, or owner's manager | | 200 `LeaveRequestOut` | 401, 404 |
| POST | `/leave-requests/{id}/approve` | owner's manager | | 200 `LeaveRequestOut` | 401, 403 not manager, 404, 409 not pending, 422 balance |
| POST | `/leave-requests/{id}/reject` | owner's manager | `{"reason": str}` (5 to 500 chars) | 200 `LeaveRequestOut` | 401, 403, 404, 409, 422 |
| DELETE | `/leave-requests/{id}` | owner | | 200 `LeaveRequestOut` (CANCELLED) | 401, 403, 404, 409 not pending |
| GET | `/notifications` | logged in | query: `unread`, `limit`, `offset` | 200 `Page[NotificationOut]`, unread first | 401 |
| POST | `/notifications/{id}/read` | recipient | | 200 `NotificationOut` | 401, 404 if not yours |
| POST | `/notifications/read-all` | logged in | | 200 `{"marked_read": n}` | 401 |
| GET | `/notifications/stream` | logged in (header or `?access_token=`) | | 200 `text/event-stream` | 401 |
| GET | `/health` | anyone | | 200 `{"status": "ok"}` | |

List rules:

- `GET /leave-requests` returns your own requests plus your direct reports'. `employee_id` narrows that set; asking for someone outside it gives an empty page, not their data.
- `sort` is one of `created_at`, `-created_at` (default), `start`, `-start`. `limit` is 1 to 100 (default 20), `offset` is 0 or more.
- Someone else's request that you may not see returns **404**, not 403, so the API does not confirm it exists.

## 3. Schemas

- `LeaveRequestCreate`: `leave_type` (ANNUAL, SICK, CASUAL), `start`, `end`, `half_day` (default false), `reason`. No `employee_id`: it comes from the token. Unknown fields are refused (422).
- `LeaveRequestOut`: `id`, `employee_id`, `leave_type`, `start`, `end`, `half_day`, `reason`, `status`, `rejection_reason`, `created_at`.
- `Page[T]`: `items`, `total`, `limit`, `offset`.
- `Token`: `access_token`, `token_type` ("bearer"), `expires_in` (seconds).
- `NotificationOut`: `id`, `event`, `request_id`, `message`, `read`, `created_at`.

## 4. Error shape

Every 4xx and 5xx has the same body:

```json
{
  "error": {
    "code": "OVERLAPPING_LEAVE",
    "message": "overlaps existing request 6f1c...",
    "request_id": "a1b2c3d4e5f6",
    "details": [{"loc": ["body", "end"], "msg": "..."}]
  }
}
```

`details` appears only on validation errors and never echoes the submitted values. `request_id` matches the `X-Request-ID` response header and the server log line.

| Status | Codes | When |
| --- | --- | --- |
| 400 | `BAD_REQUEST` | any other client error |
| 401 | `UNAUTHORIZED` | missing, bad or expired token; wrong login |
| 403 | `FORBIDDEN` | `PermissionDeniedError` |
| 404 | `NOT_FOUND` | `NotFoundError`, or a resource you may not see |
| 409 | `OVERLAPPING_LEAVE`, `INVALID_TRANSITION` | `OverlappingLeaveError`, `InvalidTransitionError` |
| 422 | `VALIDATION_ERROR`, `INSUFFICIENT_BALANCE`, `POLICY_VIOLATION` | bad input; `InsufficientBalanceError`; `PolicyViolationError` |
| 500 | `INTERNAL_ERROR` | anything unexpected (details only in the server log) |

## 5. Notifications

- Submit, approve, reject and cancel each queue `NotificationService.notify` as a FastAPI `BackgroundTask`, so the HTTP response does not wait for the (slow) email channel.
- Recipients follow SPEC.md section 3.
- The in-app channel keeps an inbox per user and pushes each new item to every open `/notifications/stream` connection as `event: notification` with the JSON as `data`. The stream sends a `: keep-alive` comment every 15 seconds.

## 6. Cross-cutting

- Settings come from environment variables prefixed `LEAVEDESK_` (or `.env`); see `.env.example`. The app refuses to start without `LEAVEDESK_JWT_SECRET` (32+ chars).
- Every request gets an id (`X-Request-ID`, generated unless the caller sends a safe one) and one log line: id, method, path, status, duration.

## 7. Acceptance criteria

- AC-1 Login with the right password returns a token; a wrong password and an unknown email give the same 401.
- AC-2 Without a token, or with a tampered one, protected endpoints return 401.
- AC-3 Applying returns 201 PENDING, uses the token's employee and queues a `submitted` notification.
- AC-4 Overlap returns 409; end before start returns 422; too few days returns 422; a weekend-only range returns 422.
- AC-5 The manager approves: 200 APPROVED, balance drops by the working days, `approved` is queued.
- AC-6 A non-manager approving gets 403; approving twice gets 409.
- AC-7 Reject stores the reason; a reason under 5 characters gets 422.
- AC-8 The owner cancels a PENDING request; cancelling an APPROVED one gets 409; the manager cannot cancel it (403).
- AC-9 A colleague asking for my request gets 404; the list filters by status, sorts and paginates.
- AC-10 Balance: self and manager can read it; a colleague gets 403.
- AC-11 The manager's inbox lists the new request unread first; `?unread=true` filters; marking someone else's notification gives 404; read-all marks all.
- AC-12 `/notifications/stream` needs a token; a subscriber receives each new notification.
- AC-13 `ruff check` and `ruff format --check` pass; `docker compose up` serves `/docs`.

## 8. Task plan (one PR each)

| PR | Task | Files |
| --- | --- | --- |
| 1 | This spec | `API_SPEC.md` |
| 2 | Foundation: settings, passwords and JWT, error shape, request-id middleware, small domain changes | `requirements*.txt`, `pyproject.toml`, `.env.example`, `api/config.py`, `api/security.py`, `api/schemas.py`, `api/errors.py`, `api/middleware.py`, `domain/{service,repository,notifications}.py` |
| 3 | Endpoints: login, balance, leave requests | `api/users.py`, `api/container.py`, `api/seed.py`, `api/deps.py`, `api/routers/{auth,employees,leave_requests}.py` |
| 4 | Notifications, SSE and the app factory | `api/routers/notifications.py`, `api/main.py` |
| 5 | Tests (AC-1 to AC-12) | `tests/` |
| 6 | Docker, README and AI notes (AC-13) | `Dockerfile`, `.dockerignore`, `docker-compose.yml`, `README.md`, `AI_NOTES.md` (Capstone 2 section) |
