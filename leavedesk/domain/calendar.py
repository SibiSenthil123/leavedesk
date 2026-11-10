"""Date helpers: working days and range overlap."""

from __future__ import annotations

from datetime import date, timedelta


def working_days(start: date, end: date, half_day: bool = False) -> float:
    """Count Monday-Friday days from start to end inclusive; a half day counts 0.5."""
    if half_day:
        return 0.5
    total_days = (end - start).days + 1
    return float(
        sum(1 for i in range(total_days) if (start + timedelta(days=i)).weekday() < 5)
    )


def ranges_overlap(a_start: date, a_end: date, b_start: date, b_end: date) -> bool:
    """Two inclusive date ranges overlap when each starts before the other ends."""
    return a_start <= b_end and b_start <= a_end
