# LeaveDesk web app: UI spec (Capstone 4)

Written **before** the code, like SPEC.md (Capstone 1), API_SPEC.md (Capstone 2) and
SCHEMA.md (Capstone 3). The Angular app talks only to the Capstone 3 API.

Stack: Angular 22 (standalone components, zoneless, signals), Angular Material, Vitest,
ESLint + Prettier. Dev server on port 4200; `/api/*` is proxied to the API on port 8000.

## Pages

| URL           | Who                 | What it shows                                                                                                 |
| ------------- | ------------------- | ------------------------------------------------------------------------------------------------------------- |
| `/login`      | everyone            | Email + password form. Wrong password shows the API's message.                                                |
| `/`           | logged-in employees | Balance cards (+ TOTAL), apply form, my requests table with status filter and paging, Cancel on PENDING rows. |
| `/approvals`  | managers only       | Pending requests from my team. Approve / Reject (reason ≥ 5 chars), each behind a confirm dialog.             |
| anything else | –                   | Sent to `/`.                                                                                                  |

The top bar shows: LeaveDesk, My leave, Approvals (managers only), my name, the bell, Log out.

## Rules (UI-1 … UI-10)

- **UI-1 Login state.** The JWT is kept in `sessionStorage` (gone when the tab closes). After a page refresh the app calls `GET /auth/me` to find out who the token belongs to.
- **UI-2 Token on every call.** An HTTP interceptor adds `Authorization: Bearer …`. Any `401` (except on the login call itself) logs the user out and sends them to `/login`.
- **UI-3 Guards.** Not logged in → every page except `/login` redirects to `/login`. Not a manager → `/approvals` redirects to `/`.
- **UI-4 Lazy pages.** My leave and Approvals are lazy-loaded: their code is downloaded only when opened.
- **UI-5 Apply form.** Leave type, start date, end date, reason (min 5 characters), half day. End date before start date shows "End date must be on or after the start date" (a cross-field validator). The Apply button stays disabled until the form is valid.
- **UI-6 Server errors are shown, not swallowed.** `409` → "Overlap: …"; `422` → the API's message (e.g. not enough days). Network down → "Cannot reach the server".
- **UI-7 State with signals.** Each feature has a small store (signals + computed). Pages read signals; only the store changes them.
- **UI-8 Optimistic approve/reject.** The row disappears at once; if the API refuses, it comes back and a snackbar explains why.
- **UI-9 Live bell.** After login the app opens `GET /notifications/stream` (Server-Sent Events). New items bump the red badge and show a snackbar; opening the bell marks all read. When a notification arrives, My leave reloads so statuses and balances are current.
- **UI-10 Usable everywhere.** Works at phone width (390px): cards wrap, tables scroll sideways. Every input has a label, errors use `role="alert"`, the bell has an `aria-label` with the unread count.

## Out of scope (stretch)

Playwright end-to-end tests, a Docker image for the web app, PWA/offline, dark-mode switch.

## How we check it

- `npx ng test --watch=false` (Vitest unit tests: validator, interceptor, stores, apply form, app shell)
- `npx ng lint` and `npx prettier --check src`
- `npx ng build`
- Live demo: Priya applies → Arjun approves → Priya's bell lights up and the row turns APPROVED.
