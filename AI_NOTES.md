# AI usage notes: Capstone 1

Fill this in honestly; reviewers score it (10 points).

| What I asked the AI | What it produced | What I changed or rejected, and why |

I asked AI to give me a step by step guide on how to navigate through github and vs code becuase I am new to this. It helped me most of the steps to move on one by one but it helped me get familiar with the usability of git and vscode. I learned how to pull code onto git and how to use the terminal in vs code 

## Issues I found in AI output

- (at least one correctness or security issue you caught, e.g. a wrong date in an example, an unused import, a rule that didn't match the spec)

AI had difficulty giving me the proper directions for downloading github and integrating github with vs code.
## Capstone 2

I relied on AI to get through the processes and flows for the prompts but I understood how the process works.

### Issues I found in AI output

- (at least one, e.g. something that didn't match API_SPEC.md, a security gap, a test that didn't really test the rule)

### Known limitations

- The SSE stream accepts the token as `?access_token=` because browsers' EventSource cannot send headers. Query strings can end up in server access logs, so a short-lived token or a cookie would be better in production.
- Users, requests and notifications live in memory and are lost on restart (PostgreSQL comes on Day 3).

## Capstone 3

Fill this in honestly; reviewers score it (10 points).

| What I asked the AI | What it produced | What I changed or rejected, and why |
| --- | --- | --- |
| | | |

### Issues I found in AI output

- (at least one. Example from the build: the first perf queries looked people up with `email = '...'`, but the unique index is on `lower(email)`, so Postgres ignored it and scanned the whole table; changing the query to `lower(email) = '...'` fixed it. Another: the first version of the test helper crashed on INSERTs because they return no rows.)

### Known limitations

- Login accounts are still in memory and rebuilt from the demo seed on each start; failed-login lockout is not built.
- In-app notifications are still in memory (lost on restart); only email goes through the database outbox.
- The repository calls the database synchronously inside async routes, which blocks the event loop for the length of each query. Fine at this size; an async engine would be the next step.
- No `tenant_id` or row-level security yet.
