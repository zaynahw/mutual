"""Mock finalization, durable replay, and concurrent/retry safety."""
import asyncio

import pytest

from backend.calendar_events import claim_event
from backend.database import connect, initialize_database
from backend.dependencies import get_calendar_adapter
from backend.friendships import create_friend_request, respond_to_friend_request, remove_friendship
from backend.hangouts import create_hangout_request
from backend.main import app
from backend.models import BusyInterval, Proposal
from backend.proposals import create_proposal, get_proposal_response, record_decision
from backend.services.calendar_adapter import MockCalendarAdapter
from backend.services.calendar_events import finalize_proposal
from backend.services.schedule import CalendarUnavailable


@pytest.fixture
def prepared(request_record):
    create_hangout_request(request_record)
    friend = create_friend_request(request_record.requester_id, request_record.invitee_id)
    respond_to_friend_request(friend.id, request_record.invitee_id, 'accept')
    proposal = Proposal(id='proposal-calendar', request_id=request_record.id, activity='coffee', slot={
        'start': '2026-10-18T15:00:00-04:00', 'end': '2026-10-18T15:30:00-04:00',
    })
    create_proposal(proposal)
    return proposal, request_record, friend


def approve(proposal, request):
    for uid in (request.requester_id, request.invitee_id):
        record_decision(proposal.id, uid, 'approve')


def finalize(proposal, request, calendar=None, key='key-1'):
    return asyncio.run(finalize_proposal(proposal.id, request.requester_id, key, calendar or MockCalendarAdapter()))


def test_success_and_durable_replay_even_with_new_adapter_and_key(prepared):
    proposal, request, _ = prepared
    approve(proposal, request)
    calendar = MockCalendarAdapter()
    response, created = finalize(proposal, request, calendar)
    assert created and response.event_id == f'demo-event-{proposal.id}'
    assert len(calendar.events) == 1
    assert get_proposal_response(proposal.id).proposal.status == 'scheduled'
    initialize_database()
    class NeverCalled:
        async def get_busy(self, *args):
            pytest.fail('Replay must not read calendars')
        async def create_event(self, *args):
            pytest.fail('Replay must not write calendars')
    assert finalize(proposal, request, NeverCalled(), 'new-key') == (response, False)


@pytest.mark.parametrize('decisions', [[], ['approve'], ['decline']])
def test_missing_approvals_and_decline_cannot_schedule(prepared, decisions):
    proposal, request, _ = prepared
    for decision in decisions:
        record_decision(proposal.id, request.requester_id, decision)
    with pytest.raises(ValueError, match='Both participants'):
        finalize(proposal, request)


@pytest.mark.parametrize('change', ['busy', 'friendship'])
def test_current_availability_and_permissions_rechecked(prepared, change):
    proposal, request, friend = prepared
    approve(proposal, request)
    calendar = MockCalendarAdapter()
    if change == 'busy':
        calendar.busy = [BusyInterval(user_id=request.invitee_id, **proposal.slot.model_dump())]
    else:
        remove_friendship(friend.id, request.requester_id)
    with pytest.raises(ValueError, match='no longer fits'):
        finalize(proposal, request, calendar)
    assert calendar.events == {}
    assert get_proposal_response(proposal.id).proposal.status == 'approved'


@pytest.mark.parametrize('phase', ['read', 'write', 'invalid-id'])
def test_calendar_failure_leaves_retryable_approved_plan(prepared, phase):
    proposal, request, _ = prepared
    approve(proposal, request)
    class Broken(MockCalendarAdapter):
        async def get_busy(self, *args):
            if phase == 'read':
                raise RuntimeError('private token')
            return []
        async def create_event(self, *args):
            if phase == 'invalid-id':
                return ''
            raise RuntimeError('private token')
    with pytest.raises(CalendarUnavailable):
        finalize(proposal, request, Broken())
    assert get_proposal_response(proposal.id).proposal.status == 'approved'
    assert finalize(proposal, request)[1] is True


def test_key_cannot_be_reused_for_another_proposal(prepared):
    proposal, request, _ = prepared
    approve(proposal, request)
    finalize(proposal, request)
    other_request = request.model_copy(update={'id': 'request-other'})
    create_hangout_request(other_request)
    other = proposal.model_copy(update={'id': 'proposal-other', 'request_id': other_request.id})
    create_proposal(other)
    approve(other, other_request)
    with pytest.raises(ValueError, match='another proposal'):
        finalize(other, other_request)


def test_overlapping_attempts_rejected_without_second_calendar_write(prepared):
    proposal, request, _ = prepared
    approve(proposal, request)
    async def scenario():
        entered, resume = asyncio.Event(), asyncio.Event()
        class Slow(MockCalendarAdapter):
            async def create_event(self, *args):
                entered.set()
                await resume.wait()
                return await super().create_event(*args)
        calendar = Slow()
        first = asyncio.create_task(finalize_proposal(proposal.id, request.requester_id, 'first', calendar))
        await entered.wait()
        try:
            with pytest.raises(ValueError, match='in progress'):
                await finalize_proposal(proposal.id, request.invitee_id, 'second', calendar)
        finally:
            resume.set()
        await first
        assert len(calendar.events) == 1
    asyncio.run(scenario())


def test_expired_crash_claim_can_be_retried(prepared):
    proposal, request, _ = prepared
    approve(proposal, request)
    claim_event(proposal.id, request.requester_id, 'old-key')
    with connect() as connection:
        connection.execute("UPDATE calendar_events SET updated_at = '2000-01-01T00:00:00+00:00'")
    assert finalize(proposal, request)[1] is True


def test_ambiguous_write_retry_uses_same_provider_key(prepared):
    proposal, request, _ = prepared
    approve(proposal, request)
    class Ambiguous(MockCalendarAdapter):
        calls = 0
        async def create_event(self, *args):
            result = await super().create_event(*args)
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError('response lost after provider succeeded')
            return result
    calendar = Ambiguous()
    with pytest.raises(CalendarUnavailable):
        finalize(proposal, request, calendar)
    assert finalize(proposal, request, calendar, 'different-client-key')[1]
    assert calendar.calls == 2 and len(calendar.events) == 1


def test_http_access_headers_errors_replay_and_cors(client, prepared):
    proposal, request, _ = prepared
    path = f'/proposals/{proposal.id}/calendar-event'
    headers = {'X-Demo-User-Id': request.requester_id, 'Idempotency-Key': 'event-key'}
    assert client.post(path).status_code == 401
    assert client.post(path, headers=headers | {'X-Demo-User-Id': 'demo-kusum'}).status_code == 404
    assert client.post(path, headers={'X-Demo-User-Id': request.requester_id}).status_code == 422
    assert client.post(path, headers=headers | {'Idempotency-Key': 'bad key'}).status_code == 422
    assert client.post(path, headers=headers).status_code == 409
    approve(proposal, request)
    app.dependency_overrides[get_calendar_adapter] = lambda: MockCalendarAdapter()
    try:
        first = client.post(path, headers=headers)
        assert first.status_code == 201
        second = client.post(path, headers=headers | {'X-Demo-User-Id': request.invitee_id})
        assert second.status_code == 200 and second.json() == first.json()
    finally:
        app.dependency_overrides.pop(get_calendar_adapter, None)
    preflight = client.options(path, headers={
        'Origin': 'http://localhost:5173', 'Access-Control-Request-Method': 'POST',
        'Access-Control-Request-Headers': 'Idempotency-Key,X-Demo-User-Id',
    })
    assert preflight.status_code == 200
