# LeaveDesk web app (Capstone 4)

The Angular front end for the LeaveDesk API. See [UI_SPEC.md](UI_SPEC.md) for what it does.

## Run it

You need the API running first (from the repo root: `docker compose up -d`).

```bash
cd web
npm install
npm start
```

Open http://localhost:4200 and log in as `priya@leavedesk.dev` (employee) or
`arjun@leavedesk.dev` (manager) with the demo password.

`npm start` uses `proxy.conf.json`: the browser calls `/api/...` on port 4200 and the
dev server forwards it to the API on port 8000, so there is no CORS setup to do.

## Check it

```bash
npx ng test --watch=false
npx ng lint
npx prettier --check src
npx ng build
```

## Folder map

```text
src/app/
├── app.ts / app.html / app.css   # top bar + <router-outlet>, opens the live bell after login
├── app.routes.ts                 # pages, guards, lazy loading
├── app.config.ts                 # HttpClient + interceptor, router
├── core/                         # used everywhere
│   ├── models.ts                 # TypeScript shapes of the API's JSON
│   ├── auth.service.ts           # token + "who am I" as signals, login/logout
│   ├── auth.interceptor.ts       # adds the Bearer token, logs out on 401
│   ├── auth.guard.ts             # authGuard, managerGuard
│   └── errors.ts                 # turns an HTTP error into a sentence
├── shared/
│   └── date-range.validator.ts   # end date must not be before start date
└── features/
    ├── login/login.page.ts
    ├── leave/                    # My leave: store, page, apply form
    ├── approvals/                # manager queue + confirm dialog (lazy)
    └── notifications/            # SSE store + bell
```
