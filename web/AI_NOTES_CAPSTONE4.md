# AI notes: Capstone 4 (Angular web app)

How AI help was used, and what was checked by hand.

- **Spec first.** UI_SPEC.md (UI-1 … UI-10) was written before any component, then each PR was checked against it.
- **Scaffolding by the CLI, not by AI.** `ng new`, `ng add @angular/material` and `ng add angular-eslint` generated the project; the AI wrote only the feature code on top.
- **Verified against the real API.** Every call was tried against the Capstone 3 API through the proxy: login, apply, a deliberate overlap (409), manager approve, and the live bell over SSE.
- **Things the AI got wrong first and we fixed:**
  - Field labels "Start"/"End" were renamed "Start date"/"End date" so they read clearly (and screen readers say the full name).
  - A unit test logged out to `/login` with no routes registered, which raised a hidden router error; the test now registers a `login` route.
  - My leave did not refresh after "approved" arrived on the bell; an `effect()` now reloads it when a notification comes in.
  - The bundle budget (500 kB) was too small for Angular Material; raised to 800 kB warning / 1.5 MB error.
- **Checks that must stay green:** `ng test`, `ng lint`, `prettier --check`, `ng build`.
