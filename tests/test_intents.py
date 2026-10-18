"""Natural requests: explicit confirmation, selected days, consent, private inputs."""
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo

import pytest

from backend.dependencies import get_agent_adapter, get_calendar_adapter
from backend.friendships import create_friend_request, respond_to_friend_request, remove_friendship
from backend.main import app
from backend.repositories import get_user
from backend.services.agent_adapter import MockAgentAdapter
from backend.services.calendar_adapter import MockCalendarAdapter
from backend.services.intent_dates import local_instant

A, B = 'demo-zaynah', 'demo-daniella'


def headers(uid=A): return {'X-Demo-User-Id': uid}


@pytest.fixture
def ready(client):
    friendship = create_friend_request(A,B)
    respond_to_friend_request(friendship.id,B,'accept')
    app.dependency_overrides[get_agent_adapter] = lambda: MockAgentAdapter()
    app.dependency_overrides[get_calendar_adapter] = lambda: MockCalendarAdapter()
    yield client, friendship
    app.dependency_overrides.pop(get_agent_adapter,None)
    app.dependency_overrides.pop(get_calendar_adapter,None)


def payload(message='I prefer morning coffee', offsets=(1,3)):
    today = datetime.now(ZoneInfo(get_user(A).timezone)).date()
    return {'invitee_id': B, 'days':[(today+timedelta(days=i)).isoformat() for i in offsets], 'message':message}


def prepare(client, body=None):
    response = client.post('/hangout-intents/interpret',headers=headers(),json=body or payload())
    assert response.status_code == 200, response.text
    return response.json()


def send(client, draft):
    return client.post(f"/hangout-intents/{draft['id']}/send",headers=headers())


def guided(client, uid=B):
    response = client.patch('/users/me/matching',headers=headers(uid),json={'mode':'calendar_guided','start_hour':9,'end_hour':21})
    assert response.status_code == 200, response.text


def candidates(client, request):
    response = client.post(f"/hangout-requests/{request['id']}/candidates",headers=headers())
    assert response.status_code == 200, response.text
    return response.json()


def test_interpret_is_private_and_send_is_confirmed_idempotent(ready):
    client,_ = ready
    draft = prepare(client)
    assert client.get('/hangout-requests',headers=headers()).json() == []
    assert client.get(f"/hangout-intents/{draft['id']}",headers=headers(B)).status_code == 404
    assert client.post(f"/hangout-intents/{draft['id']}/send",headers=headers(B)).status_code == 404
    response = send(client,draft)
    assert response.status_code == 200, response.text
    assert send(client,draft).json() == response.json()
    request = response.json()
    assert request['origin'] == 'intent' and len(request['search_windows']) == 2
    assert 'message' not in request and 'prefer morning' not in response.text
    assert len(client.get('/hangout-requests',headers=headers()).json()) == 1
    assert client.get(f"/hangout-intents/{draft['id']}",headers=headers()).json()['request_id'] == request['id']


def test_guided_matching_requires_recipient_consent_and_obeys_selected_days(ready):
    client,_ = ready
    assert get_user(B).matching.mode == 'social_windows'
    request = send(client,prepare(client)).json()
    # Future dates have no seeded social windows. A free calendar alone isn't permission.
    assert candidates(client,request) == []
    guided(client)
    options = candidates(client,request)
    assert options
    chosen_days = set(payload()['days'])
    zone = ZoneInfo(get_user(A).timezone)
    for option in options:
        start = datetime.fromisoformat(option['slot']['start']).astimezone(zone)
        end = datetime.fromisoformat(option['slot']['end']).astimezone(zone)
        assert start.date().isoformat() in chosen_days
        assert start.date() == end.date() and 9 <= start.hour < end.hour <= 21
    client.patch('/users/me/matching',headers=headers(B),json={'mode':'social_windows'})
    assert candidates(client,request) == []


def test_only_before_noon_is_hard_but_prefer_morning_keeps_afternoon(ready):
    client,_ = ready
    guided(client)
    flexible = prepare(client)
    assert flexible['result']['interpretation']['latest'] is None
    options = candidates(client,send(client,flexible).json())
    zone = ZoneInfo(get_user(A).timezone)
    assert any(datetime.fromisoformat(o['slot']['start']).astimezone(zone).hour >= 12 for o in options)
    strict = prepare(client,payload('Coffee only before noon'))
    assert strict['result']['interpretation']['latest'] == '12:00'
    options = candidates(client,send(client,strict).json())
    assert options and all(datetime.fromisoformat(o['slot']['end']).astimezone(zone).hour <= 12 for o in options)


def test_clarification_and_invalid_dates_cannot_be_silently_sent(ready):
    client,_ = ready
    draft = prepare(client,payload('Coffee at 3'))
    assert draft['result']['interpretation']['clarification']
    assert send(client,draft).status_code == 409
    for body in [payload(offsets=(-1,)),payload(offsets=(15,)),payload(offsets=(1,1)),payload('   ')]:
        assert client.post('/hangout-intents/interpret',headers=headers(),json=body).status_code == 422
    assert client.get('/hangout-requests',headers=headers()).json() == []


def test_friendship_revocation_blocks_send_and_guided_candidates(ready):
    client,friendship = ready
    guided(client)
    draft = prepare(client)
    request = send(client,prepare(client)).json()
    remove_friendship(friendship.id,A)
    assert send(client,draft).status_code == 409
    assert candidates(client,request) == []


def test_request_note_only_reaches_owner_and_suggestion_still_needs_two_approvals(ready):
    client,_ = ready
    guided(client)
    private = 'I prefer morning coffee PRIVATE_OWNER_NOTE'
    request = send(client,prepare(client,payload(private))).json()
    seen = []
    class Capture(MockAgentAdapter):
        async def negotiate(self,request,options,requester_ctx,invitee_ctx,**kwargs):
            seen.extend([requester_ctx,invitee_ctx])
            return await super().negotiate(request,options,requester_ctx,invitee_ctx,**kwargs)
    app.dependency_overrides[get_agent_adapter] = lambda: Capture()
    response = client.post(f"/hangout-requests/{request['id']}/negotiate",headers={**headers(),'Idempotency-Key':'natural-test'})
    assert response.status_code == 200, response.text
    proposal = response.json()['proposal']
    assert proposal and proposal['status'] == 'pending'
    assert seen[0].request_preferences == private and seen[0].preferred_periods == ['morning']
    assert seen[1].request_preferences == '' and seen[1].preferred_periods == []
    assert private not in response.text
    assert client.get(f"/proposals/{proposal['id']}",headers=headers()).json()['approvals'] == []


def test_matching_settings_patch_preserves_profile_and_validates_hours(ready):
    client,_ = ready
    original = client.get('/users/me',headers=headers()).json()
    guided(client,A)
    updated = client.get('/users/me',headers=headers()).json()
    assert updated['preferences'] == original['preferences']
    assert updated['calendar_sharing'] == original['calendar_sharing']
    assert client.patch('/users/me/matching',headers=headers(),json={'mode':'calendar_guided','start_hour':21,'end_hour':9}).status_code == 422
    assert client.patch('/users/me/matching',headers=headers(),json={'user_id': B}).status_code == 422


@pytest.mark.parametrize('day,clock', [(date(2026,11,1),'01:30'),(date(2026,3,8),'02:30')])
def test_dst_ambiguous_or_nonexistent_clock_requires_clarification(day,clock):
    with pytest.raises(ValueError): local_instant(day,clock,'America/New_York')


def test_explicit_between_range_is_preserved_and_compiled(ready):
    from backend.repositories import save_user
    client, _ = ready
    for uid in (A, B):
        user = get_user(uid)
        save_user(user.model_copy(update={'hard_constraints': user.hard_constraints.model_copy(update={'allowed_activities':['walk','meal']})}))
    guided(client)
    draft = prepare(client, payload('Something chill, like a walk or food. I prefer earlier in the morning. But I want this hangout somewhere between 7am and 12 pm since thats when I have the most energy', offsets=(5,)))
    parsed = draft['result']['interpretation']
    assert parsed['earliest'] == '07:00' and parsed['latest'] == '12:00'
    assert parsed['clarification'] is None
    request = send(client, draft).json()
    options = candidates(client, request)
    assert options
    zone = ZoneInfo(get_user(A).timezone)
    for option in options:
        assert datetime.fromisoformat(option['slot']['start']).astimezone(zone).hour >= 9
        assert datetime.fromisoformat(option['slot']['end']).astimezone(zone).hour <= 12


def test_backend_enforces_range_even_when_model_drops_it(ready):
    from backend.models import IntentInterpretation, IntentInterpretationResult
    client, _ = ready
    class DropsLimits(MockAgentAdapter):
        async def interpret(self, *args):
            return IntentInterpretationResult(source='local_agent', interpretation=IntentInterpretation(
                activities=['walk'], allowed_durations=[30,60], preferred_periods=['morning']))
    app.dependency_overrides[get_agent_adapter] = lambda: DropsLimits()
    parsed = prepare(client, payload('Prefer morning walks. Between 7am and 12pm'))['result']['interpretation']
    assert (parsed['earliest'], parsed['latest']) == ('07:00','12:00')


@pytest.mark.parametrize('message', ['Walk between 7 and 12', 'Walk between 7pm and 12pm', 'Walk between 7am and 12pm but only after 10am'])
def test_ambiguous_or_conflicting_range_blocks_send(ready, message):
    client, _ = ready
    draft = prepare(client, payload(message))
    assert draft['result']['interpretation']['clarification']
    assert send(client, draft).status_code == 409
