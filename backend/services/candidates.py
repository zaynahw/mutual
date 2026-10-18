"""Deterministic, activity-specific options for a two-person request.

Private profiles and raw busy intervals stay internal. Calendar browsing policy
is independent of permission to check conflicts for authorized matching.
"""
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from backend.friendships import are_friends
from backend.models import (
    BusyInterval, CandidateOption, HangoutRequest, Interval, SocialWindow, User,
)
from backend.repositories import get_user, list_social_windows
from backend.services.calendar_adapter import CalendarAdapter
from backend.services.permissions import can_access
from backend.services.schedule import CalendarUnavailable
from backend.services.scheduling import intersect_availability


def _load_participants(request: HangoutRequest) -> list[User]:
    participants = [get_user(request.requester_id), get_user(request.invitee_id)]
    if any(user is None for user in participants):
        raise LookupError("Participant not found")
    return [user for user in participants if user is not None]


def _eligible_windows(
    windows: list[SocialWindow], owner: User, participants: list[User],
    activity: str, search: Interval,
) -> list[SocialWindow]:
    # Matching-only windows are intentionally eligible here, unlike browsing.
    return [window for window in windows
            if activity in window.allowed_activities
            and window.start < search.end and window.end > search.start
            and all(can_access(owner, other, window.visibility)
                    for other in participants if other.id != owner.id)]


def _searches(request: HangoutRequest) -> list[Interval]:
    searches = request.search_windows or [Interval(start=request.start, end=request.end)]
    if request.origin != 'intent':
        return searches
    now = datetime.now(timezone.utc)
    # Stable future starts survive the fresh check after a model call.
    now = datetime.fromtimestamp((int(now.timestamp()) // 300 + 1) * 300, timezone.utc)
    return [Interval(start=max(window.start, now), end=window.end) for window in searches if window.end > now]


def _owner_windows(request: HangoutRequest, owner: User, participants: list[User], activity: str, search: Interval) -> list[Interval]:
    other = next(person for person in participants if person.id != owner.id)
    if request.join_window_id and owner.id == request.invitee_id:
        return [w for w in _eligible_windows(list_social_windows(owner.id), owner, participants, activity, search) if w.id == request.join_window_id]
    guided = owner.matching.mode == 'calendar_guided' or request.origin == 'intent' and owner.id == request.requester_id
    if not guided:
        return _eligible_windows(list_social_windows(owner.id), owner, participants, activity, search)
    # Opt-in is limited to current accepted friends, independent of browsing policy.
    if not are_friends(owner.id, other.id) and not request.join_window_id:
        return []
    zone = ZoneInfo(owner.timezone)
    day = search.start.astimezone(zone).date()
    final_day = search.end.astimezone(zone).date()
    windows = []
    while day <= final_day:
        start = datetime.combine(day, time(hour=owner.matching.start_hour), tzinfo=zone).astimezone(timezone.utc)
        end = datetime.combine(day + timedelta(days=1), time(), tzinfo=zone) if owner.matching.end_hour == 24 else datetime.combine(day, time(hour=owner.matching.end_hour), tzinfo=zone)
        if end > start:
            windows.append(Interval(start=start, end=end.astimezone(timezone.utc)))
        day += timedelta(days=1)
    return windows


def _period_slots(slot: Interval, timezone_name: str) -> list[Interval]:
    # Expose morning/afternoon/evening choices instead of just one all-day start.
    zone = ZoneInfo(timezone_name)
    day = slot.start.astimezone(zone).date()
    boundaries = {slot.start, slot.end}
    while day <= slot.end.astimezone(zone).date():
        for hour in (0, 9, 12, 17):
            boundary = datetime.combine(day, time(hour=hour), tzinfo=zone).astimezone(timezone.utc)
            if slot.start < boundary < slot.end:
                boundaries.add(boundary)
        day += timedelta(days=1)
    ordered = sorted(boundaries)
    return [Interval(start=start, end=slot.end) for start in ordered[:-1]]


def _calculate_options(
    request: HangoutRequest, participants: list[User], busy_by_user: dict[str, list[BusyInterval]],
) -> list[CandidateOption]:
    if request.join_window_id:
        owner = next(user for user in participants if user.id == request.invitee_id)
        viewer = next(user for user in participants if user.id == request.requester_id)
        window = next((w for w in list_social_windows(owner.id) if w.id == request.join_window_id), None)
        if (window is None or window.sharing_mode != 'visible'
                or (not are_friends(owner.id, viewer.id) and window.visibility.audience != 'community')
                or not can_access(owner, viewer, window.visibility)
                or request.join_window_title != window.title
                or request.start < window.start or request.end > window.end
                or any(a not in window.allowed_activities for a in request.allowed_activities)):
            return []
    activities = [activity for activity in request.allowed_activities
                  if all(activity in user.hard_constraints.allowed_activities for user in participants)]
    durations = sorted(duration for duration in request.allowed_durations
                       if all(duration <= user.hard_constraints.max_duration_minutes for user in participants))
    if not activities or not durations:
        return []
    candidates = []
    for search in _searches(request):
        for activity in activities:
            windows = [_owner_windows(request, user, participants, activity, search) for user in participants]
            slots = intersect_availability(
                windows_a=windows[0], windows_b=windows[1],
                busy_a=busy_by_user.get(participants[0].id, []), busy_b=busy_by_user.get(participants[1].id, []),
                search=search, duration_minutes=min(durations),
            )
            for slot in slots:
                choices = _period_slots(slot, participants[0].timezone) if request.origin == 'intent' else [slot]
                for choice in choices:
                    fitting = [duration for duration in durations if duration <= choice.duration_minutes]
                    if fitting:
                        candidates.append(CandidateOption(slot=choice.model_dump(), eligible_activities=[activity], eligible_durations=fitting))
    return sorted(candidates, key=lambda option: (option.slot.start, option.slot.end, option.eligible_activities[0]))


async def build_candidates(request: HangoutRequest, calendar: CalendarAdapter) -> list[CandidateOption]:
    participants = _load_participants(request)
    # Do not read calendars when permissions/windows already rule out a match.
    if not _calculate_options(request, participants, {}):
        return []

    searches = _searches(request)
    busy_by_user = {}
    try:
        for user in participants:
            busy_by_user[user.id] = []
            for search in searches:
                busy = await calendar.get_busy(user.id, search)
                busy_by_user[user.id].extend(item for item in busy if item.user_id == user.id)
    except Exception as error:
        raise CalendarUnavailable() from error

    # Reload settings and windows after external calls, and check current
    # friendships again so stale permissions don't survive a calendar wait.
    participants = _load_participants(request)
    return _calculate_options(request, participants, busy_by_user)
