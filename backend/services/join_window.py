"""Request one exact shared-window plan; publication never grants approval."""
from datetime import datetime, timezone
from uuid import uuid4

from backend.creation_receipts import get_receipt, read_receipt, save_receipt
from backend.database import connect
from backend.friendships import are_friends
from backend.models import HangoutOverview, HangoutRequest, Proposal, ProposalCreate, ProposalResponse, User
from backend.repositories import get_user, list_social_windows
from backend.services.calendar_adapter import CalendarAdapter
from backend.services.candidates import build_candidates, _calculate_options
from backend.services.permissions import can_access
from backend.services.proposals import fits_candidate


def visible_window(owner_id: str, window_id: str, viewer: User):
    owner = get_user(owner_id)
    current_viewer = get_user(viewer.id)
    window = next((w for w in list_social_windows(owner_id) if w.id == window_id), None)
    if (owner is None or current_viewer is None or owner.id == viewer.id
            or owner.is_demo != current_viewer.is_demo or window is None
            or window.sharing_mode != 'visible'
            or (not are_friends(owner.id, viewer.id) and window.visibility.audience != 'community')
            or not can_access(owner, current_viewer, window.visibility)):
        raise LookupError('Shared window not found')
    return window


async def request_join(owner_id: str, window_id: str, viewer: User, body: ProposalCreate,
                       key: str, calendar: CalendarAdapter) -> HangoutOverview:
    operation = f'join-window:{owner_id}:{window_id}'
    payload = body.model_dump(mode='json')
    replay = get_receipt(viewer.id, key, operation, payload)
    if replay is not None:
        return HangoutOverview.model_validate_json(replay)
    window = visible_window(owner_id, window_id, viewer)
    if (body.slot.start < datetime.now(timezone.utc) or body.slot.start < window.start
            or body.slot.end > window.end or body.activity not in window.allowed_activities):
        raise ValueError('Choose a future activity and time inside the shared window')
    duration = body.slot.duration_minutes
    if duration not in (30, 60, 90, 120):
        raise ValueError('Choose a duration of 30, 60, 90, or 120 minutes')
    # The explicit join request grants sender matching consent for this exact
    # interval within personal hours. It does not change global matching consent.
    request = HangoutRequest(id=f'request-{uuid4()}',requester_id=viewer.id,invitee_id=owner_id,
        start=body.slot.start,end=body.slot.end,allowed_activities=[body.activity],
        allowed_durations=[int(duration)],origin='intent',join_window_id=window_id,join_window_title=window.title)
    options = await build_candidates(request, calendar)
    if not any(fits_candidate(body, option) for option in options):
        raise ValueError('This time does not fit both calendars, personal hours, or activity boundaries')
    proposal = Proposal(**body.model_dump(),id=f'proposal-{uuid4()}',request_id=request.id,source='manual',title=window.title)
    result = HangoutOverview(request=request,proposals=[ProposalResponse(proposal=proposal,approvals=[])])
    with connect() as connection:
        connection.execute('BEGIN IMMEDIATE')
        replay = read_receipt(connection,viewer.id,key,operation,payload)
        if replay is not None:
            return HangoutOverview.model_validate_json(replay)
        # The write lock prevents permissions/windows changing between this
        # final eligibility check and insertion. No provider calls in transaction.
        visible_window(owner_id,window_id,viewer)
        if not any(fits_candidate(body, option) for option in _calculate_options(
                    request,[get_user(viewer.id),get_user(owner_id)],{})):
            raise ValueError('Shared availability changed; refresh the schedule')
        connection.execute('INSERT INTO hangout_requests (id,requester_id,invitee_id,data) VALUES (?,?,?,?)',
                           (request.id,viewer.id,owner_id,request.model_dump_json()))
        connection.execute('INSERT INTO proposals (id,request_id,data) VALUES (?,?,?)',
                           (proposal.id,request.id,proposal.model_dump_json()))
        save_receipt(connection,viewer.id,key,operation,payload,result.model_dump_json())
    return result
