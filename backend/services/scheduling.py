"""Pure interval operations. Call only after backend authorization.

Half-open intervals [start, end); touching busy intervals do not conflict.
Return maximal common free intervals long enough for the requested duration.
No ranking, agent behavior, persistence, or event creation occurs here.
"""
from datetime import timedelta, timezone
from backend.models import Interval, CandidateSlot


def _merge(intervals: list[Interval]) -> list[tuple]:
    result = []
    for interval in sorted(intervals, key=lambda i: i.start):
        start, end = interval.start.astimezone(timezone.utc), interval.end.astimezone(timezone.utc)
        if result and start <= result[-1][1]:
            result[-1] = (result[-1][0], max(result[-1][1], end))
        else:
            result.append((start, end))
    return result


def intersect_availability(
    windows_a: list[Interval], windows_b: list[Interval],
    busy_a: list[Interval], busy_b: list[Interval],
    search: Interval, duration_minutes: int,
) -> list[CandidateSlot]:
    if isinstance(duration_minutes, bool) or not isinstance(duration_minutes, int) or duration_minutes <= 0:
        raise ValueError("duration_minutes must be a positive integer")
    common = []
    for a_start, a_end in _merge(windows_a):
        for b_start, b_end in _merge(windows_b):
            start, end = max(a_start, b_start, search.start), min(a_end, b_end, search.end)
            if start < end:
                common.append(Interval(start=start, end=end))
    free = _merge(common)
    for busy_start, busy_end in _merge([*busy_a, *busy_b]):
        remaining = []
        for start, end in free:
            if busy_end <= start or busy_start >= end:
                remaining.append((start, end))
            else:
                if start < busy_start:
                    remaining.append((start, busy_start))
                if busy_end < end:
                    remaining.append((busy_end, end))
        free = remaining
    minimum = timedelta(minutes=duration_minutes)
    return [CandidateSlot(start=start, end=end) for start, end in free if end - start >= minimum]
