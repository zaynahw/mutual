"""Deterministic, activity-specific options for a two-person request.

Private profiles and raw busy intervals stay internal. Calendar browsing policy
is independent of permission to check conflicts for authorized matching.
"""
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


def _calculate_options(
    request: HangoutRequest, participants: list[User],
    busy_by_user: dict[str, list[BusyInterval]],
) -> list[CandidateOption]:
    activities = [activity for activity in request.allowed_activities
                  if all(activity in user.hard_constraints.allowed_activities for user in participants)]
    durations = sorted(duration for duration in request.allowed_durations
                       if all(duration <= user.hard_constraints.max_duration_minutes for user in participants))
    if not activities or not durations:
        return []

    search = Interval(start=request.start, end=request.end)
    windows_by_user = {user.id: list_social_windows(user.id) for user in participants}
    candidates = []
    for activity in activities:
        windows = [_eligible_windows(windows_by_user[user.id], user, participants, activity, search)
                   for user in participants]
        # The public request model still has exactly two participants.
        slots = intersect_availability(
            windows_a=windows[0], windows_b=windows[1],
            busy_a=busy_by_user.get(participants[0].id, []),
            busy_b=busy_by_user.get(participants[1].id, []),
            search=search, duration_minutes=min(durations),
        )
        for slot in slots:
            candidates.append(CandidateOption(
                slot=slot, eligible_activities=[activity],
                eligible_durations=[duration for duration in durations if duration <= slot.duration_minutes],
            ))
    return sorted(candidates, key=lambda option: (
        option.slot.start, option.slot.end, option.eligible_activities[0],
    ))


async def build_candidates(request: HangoutRequest, calendar: CalendarAdapter) -> list[CandidateOption]:
    participants = _load_participants(request)
    # Do not read calendars when permissions/windows already rule out a match.
    if not _calculate_options(request, participants, {}):
        return []

    search = Interval(start=request.start, end=request.end)
    busy_by_user = {}
    try:
        for user in participants:
            busy = await calendar.get_busy(user.id, search)
            busy_by_user[user.id] = [item for item in busy if item.user_id == user.id]
    except Exception as error:
        raise CalendarUnavailable() from error

    # Reload settings and windows after external calls, and check current
    # friendships again so stale permissions don't survive a calendar wait.
    participants = _load_participants(request)
    return _calculate_options(request, participants, busy_by_user)
