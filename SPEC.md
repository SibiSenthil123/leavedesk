# LeaveDesk: Capstone 1 specification

LeaveDesk lets employees request leave and managers approve or reject it. Capstone 1 covers the domain rules in plain Python: no web framework or database yet.

## 1. Entities

| Entity | Fields | Notes |
| --- | --- | --- |
| Employee | id, name, email, manager_id | `manager_id` is `None` for someone with no manager |
| Manager | an Employee that other employees point to via `manager_id` | not a separate class |
| LeaveType | ANNUAL, SICK, CASUAL | enum |
| LeaveRequest | id, employee_id, leave_type, start, end, half_day, reason, status, rejection_reason, created_at | Pydantic model |
| LeaveBalance | employee_id, leave_type, entitled, used, remaining (= entitled - used) | one per employee per leave type |
| Notification | id, recipient_id, event, request_id, message, read, created_at | `read` starts False |

## 2. Status transitions

| From | Allowed to | Who |
| --- | --- | --- |
| PENDING | APPROVED | the employee's manager |
| PENDING | REJECTED (reason required) | the employee's manager |
| PENDING | CANCELLED | the employee who applied |
| APPROVED, REJECTED, CANCELLED | nothing (final) | |

Any other change raises `InvalidTransitionError`.

## 3. Notification rules

| Event | Recipient |
| --- | --- |
| submitted | the employee's manager |
| approved | the employee |
| rejected | the employee (message includes the reason) |
| cancelled | the employee's manager |

Each notification goes through every channel (email, in-app) concurrently.

## 4. Balance rule

Balance is **checked on apply** and **deducted on approve**. Approve re-checks it, because other requests may have been approved in between.

## 5. Functional requirements

**FR-1 Working-day count**
- AC-1.1 Given a range Mon 9 to Fri 13 Nov 2026, when days are counted, then the result is 5.
- AC-1.2 Given Fri 13 to Mon 16 Nov 2026, when days are counted, then the result is 2 (weekend skipped).
- AC-1.3 Given a half-day request, when days are counted, then the result is 0.5.

**FR-2 Apply for leave**
- AC-2.1 Given Priya has 10 annual days, when she applies for 9 to 13 Nov, then a PENDING request is stored and her manager is notified.
- AC-2.2 Given Priya has 5 annual days left, when she applies for 10 working days, then `InsufficientBalanceError` is raised and nothing is stored.
- AC-2.3 Given an APPROVED request for 9 to 13 Nov, when Priya applies for 12 to 17 Nov, then `OverlappingLeaveError` is raised.
- AC-2.4 Given a range with no working days (Sat to Sun), when she applies, then `PolicyViolationError` is raised.

**FR-3 Approve**
- AC-3.1 Given a PENDING request of 5 days, when her manager approves it, then status is APPROVED, 5 days are deducted and Priya is notified.
- AC-3.2 Given an APPROVED request, when anyone approves it again, then `InvalidTransitionError` is raised.
- AC-3.3 Given a PENDING request, when someone who is not her manager approves it, then `PermissionDeniedError` is raised.

**FR-4 Reject**
- AC-4.1 Given a PENDING request, when her manager rejects it with a reason, then status is REJECTED, the reason is stored and Priya is notified with it.
- AC-4.2 Given a reason under 5 characters, when rejecting, then the rejection is refused.

**FR-5 Cancel**
- AC-5.1 Given her own PENDING request, when Priya cancels it, then status is CANCELLED and her manager is notified.
- AC-5.2 Given an APPROVED request, when Priya cancels it, then `InvalidTransitionError` is raised.

**FR-6 Leave-type policies**
- AC-6.1 Annual leave cannot start before today.
- AC-6.2 Sick leave may start up to 7 days in the past but at most 2 days ahead.
- AC-6.3 Casual leave is limited to 2 working days per request.

**FR-7 Notifications**
- AC-7.1 Given one event with 2 channels and a 0.2 s email channel, when notifications are sent, then the total time is about 0.2 s, not 0.4 s.
- AC-7.2 After the happy path, the in-app inbox shows unread counts per user.

## 6. Validation rules

- `end >= start`
- `reason` is 5 to 500 characters after trimming spaces
- `half_day` only when `start == end`
- `status` only from the allowed set (enforced by the enum, also on later assignment)
- `email` must look like an email address

## 7. Edge cases

| # | Case | Expected |
| --- | --- | --- |
| EC-1 | end date before start date | Pydantic `ValidationError` |
| EC-2 | weekends inside a range | not counted; a weekend-only range is refused with `PolicyViolationError` |
| EC-3 | overlap with a PENDING or APPROVED request | `OverlappingLeaveError` (REJECTED and CANCELLED don't count) |
| EC-4 | insufficient balance | `InsufficientBalanceError` |
| EC-5 | half-day leave | counts 0.5; a half day across two dates is a `ValidationError` |

## 8. Task breakdown

| Task | Implements | File |
| --- | --- | --- |
| Exceptions | EC-3, EC-4, transitions | `leavedesk/domain/exceptions.py` |
| Pydantic models and validators | validation rules, EC-1, EC-5 | `leavedesk/domain/models.py` |
| Working days and overlap | FR-1, EC-2, EC-3 | `leavedesk/domain/calendar.py` |
| LeaveBalance | balance rule, EC-4 | `leavedesk/domain/balance.py` |
| Leave policies | FR-6 | `leavedesk/domain/policy.py` |
| Repository | storage for FR-2 to FR-5 | `leavedesk/domain/repository.py` |
| LeaveService | FR-2 to FR-5 | `leavedesk/domain/service.py` |
| @audit and timed() | audit logging | `leavedesk/domain/audit.py` |
| Notifications | notification rules, FR-7 | `leavedesk/domain/notifications.py` |
| Demo | every AC and EC above | `leavedesk/demo.py` |
