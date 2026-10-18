"""Recovery and retry behavior exercised through the actual demo endpoints."""
import asyncio
from concurrent.futures import ThreadPoolExecutor

import pytest

from backend.calendar_events import claim_event, release_event
from backend.database import connect
from backend.dependencies import get_calendar_adapter
from backend.friendships import create_friend_request, respond_to_friend_request
from backend.hangouts import create_hangout_request, list_hangout_requests
from backend.main import app
from backend.models import Proposal, ProposalCreate, Interval
from backend.proposals import create_proposal, get_proposal_response, list_proposals_for_request, record_decision, replan_proposal
from backend.repositories import get_user, save_user
from backend.services.calendar_adapter import MockCalendarAdapter
from backend.services.calendar_events import finalize_proposal
from backend.services.demo_calendar import DemoCalendarAdapter
from backend.services.proposals import create_validated_proposal


@pytest.fixture
def prepared(client, request_record):
    create_hangout_request(request_record)
    friend = create_friend_request(request_record.requester_id, request_record.invitee_id)
    respond_to_friend_request(friend.id, request_record.invitee_id, 'accept')
    app.dependency_overrides[get_calendar_adapter] = lambda: DemoCalendarAdapter()
    yield client, request_record
    app.dependency_overrides.pop(get_calendar_adapter, None)


def headers(uid='demo-zaynah', key=None):
    return {'X-Demo-User-Id':uid} | ({'Idempotency-Key':key} if key else {})


def plan():
    return {'activity':'coffee','slot':{'start':'2026-10-18T15:00:00-04:00','end':'2026-10-18T15:30:00-04:00'}}


def test_manual_creation_counts_as_only_authors_approval_and_replays(prepared):
    client, request = prepared
    path = f'/hangout-requests/{request.id}/proposals'
    first = client.post(path, headers=headers(key='retry'), json=plan())
    assert first.status_code == 201
    pid = first.json()['id']
    replay = client.post(path, headers=headers(key='retry'), json=plan())
    assert replay.json() == first.json()
    assert len(list_proposals_for_request(request.id)) == 1
    result = get_proposal_response(pid)
    assert result.proposal.status == 'pending'
    assert [item.user_id for item in result.approvals] == [request.requester_id]
    assert client.post(path, headers=headers(key='retry'), json=plan() | {'activity':'walk'}).status_code == 409
    assert client.post(f'/proposals/{pid}/approvals', headers=headers(request.invitee_id), json={'decision':'approve'}).json()['proposal']['status'] == 'approved'
    assert client.post(path, headers=headers(key='retry'), json=plan()).json() == first.json()


def test_internal_agent_recommendation_does_not_approve_for_anyone(prepared):
    _, request = prepared
    proposal = asyncio.run(create_validated_proposal(request, ProposalCreate.model_validate(plan()), MockCalendarAdapter()))
    assert get_proposal_response(proposal.id).approvals == []


def test_hangout_creation_receipt_is_actor_and_payload_bound(prepared):
    client, request = prepared
    body = request.model_dump(mode='json',exclude={'id','requester_id','origin','join_window_id','join_window_title'})
    response = client.post('/hangout-requests',headers=headers(key='request-key'),json=body)
    assert response.status_code == 201
    assert client.post('/hangout-requests',headers=headers(key='request-key'),json=body).json() == response.json()
    assert len(list_hangout_requests(request.requester_id)) == 2
    assert client.post('/hangout-requests',headers=headers(key='request-key'),json=body | {'location':'different'}).status_code == 409
    other_body = body | {'invitee_id':request.requester_id}
    other = client.post('/hangout-requests',headers=headers(request.invitee_id,'request-key'),json=other_body)
    assert other.status_code == 201 and other.json()['id'] != response.json()['id']


def test_concurrent_manual_retries_save_one_plan_and_one_approval(prepared):
    _, request = prepared
    def create(_):
        return asyncio.run(create_validated_proposal(request,ProposalCreate.model_validate(plan()),MockCalendarAdapter(),request.requester_id,'same-key'))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(create,range(2)))
    assert results[0].id == results[1].id
    assert len(get_proposal_response(results[0].id).approvals) == 1


def test_stale_approved_plan_can_be_closed_and_replaced_with_fresh_approvals(prepared):
    client, request = prepared
    pid = client.post(f'/hangout-requests/{request.id}/proposals',headers=headers(),json=plan()).json()['id']
    record_decision(pid,request.invitee_id,'approve')
    user = get_user(request.requester_id)
    save_user(user.model_copy(update={'hard_constraints':user.hard_constraints.model_copy(update={'allowed_activities':['study']})}))
    assert client.post(f'/proposals/{pid}/calendar-event',headers=headers(key='schedule')).status_code == 409
    result = client.post(f'/proposals/{pid}/replan',headers=headers(request.invitee_id))
    assert result.status_code == 200 and result.json()['proposal']['status'] == 'cancelled'
    assert len(result.json()['approvals']) == 2
    assert client.post(f'/proposals/{pid}/replan',headers=headers()).json() == result.json()
    save_user(user)
    new = client.post(f'/hangout-requests/{request.id}/proposals',headers=headers(),json=plan()).json()
    assert new['id'] != pid
    assert len(get_proposal_response(new['id']).approvals) == 1
    assert get_proposal_response(new['id']).proposal.status == 'pending'


def test_replan_closes_alternatives_and_checks_access(prepared):
    client, request = prepared
    base = Proposal(id='a',request_id=request.id,**plan())
    create_proposal(base); create_proposal(base.model_copy(update={'id':'b'}))
    record_decision('a',request.requester_id,'approve'); record_decision('a',request.invitee_id,'approve')
    assert client.post('/proposals/a/replan',headers=headers('demo-kusum')).status_code == 404
    assert client.post('/proposals/a/replan').status_code == 401
    replan_proposal('a',request.requester_id)
    assert {item.status for item in list_proposals_for_request(request.id)} == {'cancelled'}
    with pytest.raises(ValueError):
        record_decision('b',request.invitee_id,'approve')


def test_replan_cannot_race_calendar_claim_or_erase_ambiguous_write(prepared):
    _, request = prepared
    proposal = Proposal(id='event',request_id=request.id,**plan());create_proposal(proposal)
    for uid in (request.requester_id,request.invitee_id):record_decision(proposal.id,uid,'approve')
    claim = claim_event(proposal.id,request.requester_id,'key')
    with pytest.raises(ValueError):replan_proposal(proposal.id,request.requester_id)
    release_event(claim)
    with connect() as connection:
        connection.execute('UPDATE calendar_events SET external_started = 1')
    with pytest.raises(ValueError):replan_proposal(proposal.id,request.requester_id)


def test_mock_booking_becomes_busy_for_both_and_overview_is_private(prepared):
    client, request = prepared
    proposal = Proposal(id='booked',request_id=request.id,**plan());create_proposal(proposal)
    for uid in (request.requester_id,request.invitee_id):record_decision(proposal.id,uid,'approve')
    asyncio.run(finalize_proposal(proposal.id,request.requester_id,'key',DemoCalendarAdapter()))
    for uid in (request.requester_id,request.invitee_id):
        busy = asyncio.run(DemoCalendarAdapter().get_busy(uid,Interval(start=request.start,end=request.end)))
        assert len(busy) == 1 and busy[0].start == proposal.slot.start
        summary = client.get('/hangout-requests/overview',headers=headers(uid))
        assert summary.status_code == 200
        assert summary.json()[0]['proposals'][0]['proposal']['status'] == 'scheduled'
    assert client.get('/hangout-requests/overview',headers=headers('demo-kusum')).json() == []
    assert client.get('/hangout-requests/overview').status_code == 401
    with pytest.raises(ValueError):replan_proposal(proposal.id,request.requester_id)
    followup = request.model_copy(update={'id':'followup'});create_hangout_request(followup)
    with pytest.raises(ValueError,match='no longer fits'):
        asyncio.run(create_validated_proposal(followup,ProposalCreate.model_validate(plan()),DemoCalendarAdapter()))
