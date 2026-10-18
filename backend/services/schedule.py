"""Project authorized social windows and calendar free/busy for browsing.

This does not calculate matching candidates or create events. Matching-only
windows are visible to their owner but never to another schedule viewer.
"""
from datetime import timezone

from backend.models import Interval, PublicUser, ScheduleResponse, SharedSocialWindow, User
from backend.repositories import list_social_windows
from backend.services.calendar_adapter import CalendarAdapter
from backend.services.permissions import can_access


class CalendarUnavailable(Exception):
    """Adapter failed; callers must return a generic error without private data."""


def clip_interval(interval: Interval, search: Interval) -> Interval | None:
    start = max(interval.start.astimezone(timezone.utc), search.start.astimezone(timezone.utc))
    end = min(interval.end.astimezone(timezone.utc), search.end.astimezone(timezone.utc))
    return Interval(start=start, end=end) if start < end else None


async def build_schedule(
    owner: User, viewer: User, search: Interval, calendar: CalendarAdapter,
) -> ScheduleResponse:
    calendar_busy = None
    if can_access(owner, viewer, owner.calendar_sharing):
        try:
            busy = await calendar.get_busy(owner.id, search)
            # Ignore any other user's intervals even if an adapter returns them.
            clipped = [clip_interval(item, search) for item in busy if item.user_id == owner.id]
        except Exception as error:
            raise CalendarUnavailable() from error
        # Recheck friendship after waiting on an external calendar service.
        if can_access(owner, viewer, owner.calendar_sharing):
            calendar_busy = sorted(
                [item for item in clipped if item is not None], key=lambda item: (item.start, item.end),
            )

    social_windows = []
    for window in list_social_windows(owner.id):
        if owner.id != viewer.id and window.sharing_mode == 'matching_only':
            continue
        if not can_access(owner, viewer, window.visibility):
            continue
        clipped = clip_interval(window, search)
        if clipped is not None:
            social_windows.append(SharedSocialWindow(
                id=window.id, title=window.title, start=clipped.start, end=clipped.end,
                allowed_activities=window.allowed_activities,
            ))
    social_windows.sort(key=lambda window: (window.start, window.end, window.id))
    return ScheduleResponse(
        user=PublicUser(id=owner.id, display_name=owner.display_name,
                        is_demo=owner.is_demo, community=owner.community),
        social_windows=social_windows,
        calendar_busy=calendar_busy,
    )
