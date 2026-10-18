"""Proposal HTTP access, fresh validation, and failure response boundaries."""
import pytest

from backend.dependencies import get_calendar_adapter
from backend.friendships import create_friend_request, respond_to_friend_request
from backend.hangouts import create_hangout_request
from backend.main import app
from backend.proposals import list_proposals_for_request
from backend.services.calendar_adapter import MockCalendarAdapter


@pytest.fixture
def prepared(client, request_record):
    create_hangout_request(request_record)
    friend = create_friend_request(request_record.requester_id, request_record.invitee_id)
    respond_to_friend_request(friend.id, request_record.invitee_id, 'accept')
    app.dependency_overrides[get_calendar_adapter] = lambda: MockCalendarAdapter()
    yield client, request_record
    app.dependency_overrides.pop(get_calendar_adapter, None)


def headers(user_id):
    return {'X-Demo-User-Id': user_id}


def plan():
    return {'activity': 'coffee', 'slot': {
        'start': '2026-10-18T15:00:00-04:00',
        'end': '2026-10-18T15:30:00-04:00',
    }}


def test_create_and_both_participants_view_pending_plan(prepared):
    client, request = prepared
    response = client.post(f'/hangout-requests/{request.id}/proposals',
                           headers=headers(request.requester_id), json=plan())
    assert response.status_code == 201
    proposal = response.json()
    assert proposal['status'] == 'pending'
    assert proposal['request_id'] == request.id
    assert proposal['location'] == request.location
    for user_id in (request.requester_id, request.invitee_id):
        result = client.get(f"/proposals/{proposal['id']}", headers=headers(user_id))
        assert result.status_code == 200
        assert result.json() == {'proposal': proposal, 'approvals': []}


def test_invitee_can_create(prepared):
    client, request = prepared
    assert client.post(f'/hangout-requests/{request.id}/proposals',
                       headers=headers(request.invitee_id), json=plan()).status_code == 201


def test_invalid_current_availability_returns_conflict_without_saving(prepared):
    client, request = prepared
    response = client.post(f'/hangout-requests/{request.id}/proposals',
                           headers=headers(request.requester_id), json=plan() | {'activity': 'walk'})
    assert response.status_code == 409
    assert list_proposals_for_request(request.id) == []


def test_calendar_failure_is_generic_and_does_not_save(prepared):
    class BrokenCalendar:
        async def get_busy(self, user_id, search):
            raise RuntimeError('secret token and private calendar')
    client, request = prepared
    app.dependency_overrides[get_calendar_adapter] = lambda: BrokenCalendar()
    response = client.post(f'/hangout-requests/{request.id}/proposals',
                           headers=headers(request.requester_id), json=plan())
    assert response.status_code == 502
    assert response.json() == {'detail': 'Calendar availability is temporarily unavailable'}
    assert list_proposals_for_request(request.id) == []


def test_missing_and_nonparticipant_records_are_concealed(prepared):
    client, request = prepared
    owner = headers(request.requester_id)
    outsider = headers('demo-kusum')
    proposal = client.post(f'/hangout-requests/{request.id}/proposals', headers=owner, json=plan()).json()
    real = client.get(f"/proposals/{proposal['id']}", headers=outsider)
    missing = client.get('/proposals/missing', headers=outsider)
    assert real.status_code == missing.status_code == 404
    assert real.json() == missing.json()
    for request_id in (request.id, 'missing'):
        response = client.post(f'/hangout-requests/{request_id}/proposals', headers=outsider, json=plan())
        assert response.status_code == 404
    assert len(list_proposals_for_request(request.id)) == 1


def test_identity_required_for_both_routes(prepared):
    client, request = prepared
    assert client.post(f'/hangout-requests/{request.id}/proposals', json=plan()).status_code == 401
    assert client.get('/proposals/missing').status_code == 401


@pytest.mark.parametrize('extra', [
    {'status': 'approved'}, {'request_id': 'other'}, {'id': 'chosen'}, {'location': 'override'},
])
def test_server_fields_cannot_be_supplied(prepared, extra):
    client, request = prepared
    response = client.post(f'/hangout-requests/{request.id}/proposals',
                           headers=headers(request.requester_id), json=plan() | extra)
    assert response.status_code == 422
    assert list_proposals_for_request(request.id) == []
