# LeaveDesk

Employee leave management. Capstone 1: the domain rules in plain Python (no web framework or database yet). See [SPEC.md](SPEC.md).

## Setup

Requires Python 3.12 or newer.

**Mac / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows (PowerShell)**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run the demo

```bash
python -m leavedesk.demo
```

It runs the happy path (apply, approve, reject, cancel) and every edge case from the spec, printing `PASS` or `FAIL` for each, and ends with `N/N checks passed`. The exit code is 1 if any check fails.

## Layout

```text
leavedesk/
├── demo.py                 # runnable walkthrough of every rule
└── domain/
    ├── exceptions.py       # business rule errors
    ├── models.py           # Pydantic models: Employee, LeaveRequest, Notification
    ├── calendar.py         # working days, overlap
    ├── balance.py          # LeaveBalance dataclass
    ├── policy.py           # LeavePolicy + Annual / Sick / Casual
    ├── repository.py       # LeaveRepository Protocol + in-memory version
    ├── service.py          # LeaveService: apply, approve, reject, cancel
    ├── audit.py            # @audit decorator, timed() context manager
    └── notifications.py    # Notifier, EmailNotifier, InAppNotifier, NotificationService
```
