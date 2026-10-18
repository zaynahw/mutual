"""Validate plans against actual candidate calculation and isolated SQLite data."""
import asyncio

import pytest

from backend.friendships import create_friend_request, remove_friendship, respond_to_friend_request
from backend.hangouts import create_hangout_request
from backend.models import BusyInterval, ProposalCreate, SocialWindow, User
from backend.proposals import get_proposal, list_proposals_for_request
from backend.repositories import get_user, list_social_windows, save_user, update_social_window
from backend.services.calendar_adapter import MockCalendarAdapter
from backend.services.proposals import create_validated_proposal
from backend.services.schedule import CalendarUnavailable


@pytest.fixture
def prepared(request_record):
    create_hangout_request(request_record)
    friend = create_friend_request(request_record.requester_id, request_record.invitee_id)
    respond_to_friend_request(friend.id, request_record.invitee_id, 'accept')
    return request_record, friend


def recommendation(activity='coffee', start='15:00', end='15:30'):
    return ProposalCreate(activity=activity, slot={
        'start':f'2026-10-18T{start}:00-04:00', 'end':f'2026-10-18T{end}:00-04:00',
    })


def propose(request, plan, calendar=None):
    return asyncio.run(create_validated_proposal(request, plan, calendar or MockCalendarAdapter()))


def test_valid_recommendation_saved_pending_with_inherited_location(prepared):
    request, _ = prepared
    plan = recommendation()
    proposal = propose(request, plan)
    assert proposal.status == 'pending'
    assert proposal.request_id == request.id
    assert proposal.location == request.location
    assert proposal.activity == plan.activity
    assert proposal.slot == plan.slot
    assert get_proposal(proposal.id) == proposal
    assert propose(request, plan).id != proposal.id


@pytest.mark.parametrize('plan', [
    recommendation('walk'), recommendation('meal'),
    recommendation(start='15:00',end='17:00'),
    recommendation(start='14:00',end='14:30'),
    recommendation(start='14:45',end='15:15'),
    recommendation(start='17:45',end='18:15'),
])
def test_invalid_choices_and_partial_containment_not_saved(prepared,plan):
    request, _ = prepared
    with pytest.raises(ValueError,match='no longer fits'):
        propose(request,plan)
    assert list_proposals_for_request(request.id) == []


def test_calendar_changes_invalidate_previously_possible_choice(prepared):
    request, _ = prepared
    plan = recommendation()
    original = propose(request,plan)
    busy = BusyInterval(user_id=request.invitee_id,start=plan.slot.start,end=plan.slot.end)
    with pytest.raises(ValueError):
        propose(request,plan,MockCalendarAdapter([busy]))
    assert list_proposals_for_request(request.id) == [original]


def test_cannot_span_busy_gap_between_two_candidates(prepared):
    request, _ = prepared
    busy = BusyInterval(user_id=request.invitee_id,start='2026-10-18T16:00:00-04:00',end='2026-10-18T16:15:00-04:00')
    with pytest.raises(ValueError):
        propose(request,recommendation(start='15:45',end='16:15'),MockCalendarAdapter([busy]))
    assert list_proposals_for_request(request.id) == []


@pytest.mark.parametrize('change',['window','constraint','friendship'])
def test_current_settings_and_permissions_are_used(prepared,change):
    request, friend = prepared
    if change == 'window':
        window = next(item for item in list_social_windows(request.invitee_id) if item.id == 'window-2')
        updated = SocialWindow.model_validate(window.model_dump() | {'visibility': {'audience':'private'}})
        update_social_window(updated)
    elif change == 'constraint':
        user = get_user(request.invitee_id)
        save_user(User.model_validate(user.model_dump() | {
            'hard_constraints': {'allowed_activities':['study'],'max_duration_minutes':120},
        }))
    else:
        remove_friendship(friend.id,request.requester_id)
    with pytest.raises(ValueError):
        propose(request,recommendation())
    assert list_proposals_for_request(request.id) == []


def test_calendar_failure_does_not_save_proposal(prepared):
    class UnavailableCalendar:
        async def get_busy(self,user_id,search):
            raise RuntimeError('private error')
    request, _ = prepared
    with pytest.raises(CalendarUnavailable):
        propose(request,recommendation(),UnavailableCalendar())
    assert list_proposals_for_request(request.id) == []


def test_equivalent_utc_recommendation_and_exact_candidate_edges(prepared):
    request, _ = prepared
    plan = ProposalCreate(activity='coffee',slot={'start':'2026-10-18T19:00:00Z','end':'2026-10-18T20:00:00Z'})
    assert propose(request,plan).slot == plan.slot
