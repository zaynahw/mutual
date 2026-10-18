"""Resolve selected dates in the requester's timezone; never ask the LLM for UTC."""
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo


def local_instant(day: date, clock: str, zone: str) -> datetime:
    wall = datetime.combine(day, time.fromisoformat(clock))
    tz = ZoneInfo(zone)
    possibilities = set()
    for fold in (0, 1):
        instant = wall.replace(tzinfo=tz, fold=fold).astimezone(timezone.utc)
        if instant.astimezone(tz).replace(tzinfo=None) == wall:
            possibilities.add(instant)
    if len(possibilities) != 1:
        raise ValueError('A selected time is ambiguous or does not exist because the clocks change; choose another time or day')
    return possibilities.pop()
