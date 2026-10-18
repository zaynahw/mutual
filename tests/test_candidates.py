"""Candidate calculation through the real API and injected calendar boundary."""
import pytest
from fastapi.testclient import TestClient

from backend.database import connect
from backend.dependencies import get_calendar_adapter
from backend.friendships import create_friend_request, remove_friendship, respond_to_friend_request
from backend.main import app
from backend.models import BusyInterval, CandidateOption, SocialWindow, User, VisibilityPolicy
from backend.repositories import create_social_window, get_user, save_user


class Calendar:
    def __init__(self):
        self.calls = []
        self.busy = []
        self.fail_user = None
        self.on_read = None

    async def get_busy(self, user_id, search):
        self.calls.append(user_id)
        if self.on_read:
            self.on_read(user_id)
        if user_id == self.fail_user:
            raise RuntimeError('SECRET TOKEN')
        # Deliberately return mixed owners to check backend filtering.
        return self.busy


def span(start='14:00', end='18:00'):
    return {'start': f'2026-10-18T{start}:00-04:00', 'end': f'2026-10-18T{end}:00-04:00'}


def window(id, owner, activities, start='14:00', end='18:00', audience='community', mode='visible', selected=None):
    return SocialWindow(id=id, user_id=owner, **span(start,end), allowed_activities=activities,
                        visibility=VisibilityPolicy(audience=audience, selected_friend_ids=selected or []), sharing_mode=mode)


@pytest.fixture
def setup(seeded_database):
    with connect() as connection:
        connection.execute('DELETE FROM social_windows')
    for identity in ('demo-zaynah','demo-daniella'):
        user = get_user(identity)
        save_user(User.model_validate(user.model_dump() | {
            'hard_constraints': {'allowed_activities':['coffee','walk'], 'max_duration_minutes':120},
            'calendar_sharing': {'audience':'private'},
        }))
    create_social_window(window('a','demo-zaynah',['coffee','walk']))
    create_social_window(window('b','demo-daniella',['coffee','walk']))
    calendar = Calendar()
    app.dependency_overrides[get_calendar_adapter] = lambda: calendar
    try:
        with TestClient(app) as client:
            response = client.post('/hangout-requests', headers={'X-Demo-User-Id':'demo-zaynah'}, json={
                **span(), 'invitee_id':'demo-daniella', 'allowed_activities':['coffee','walk'],
                'allowed_durations':[30,60,120], 'location':'Tech Square',
            })
            assert response.status_code == 201
            yield client, calendar, response.json()['id']
    finally:
        app.dependency_overrides.pop(get_calendar_adapter, None)


def options(setup, viewer='demo-zaynah'):
    client, _, request_id = setup
    return client.post(f'/hangout-requests/{request_id}/candidates', headers={'X-Demo-User-Id':viewer})


def test_activity_options_are_separate_and_private_calendar_still_checked(setup):
    _, calendar, _ = setup
    response = options(setup)
    assert response.status_code == 200
    assert [item['eligible_activities'] for item in response.json()] == [['coffee'],['walk']]
    assert calendar.calls == ['demo-zaynah','demo-daniella']
    for item in response.json():
        CandidateOption.model_validate(item)
        assert item['eligible_durations'] == [30,60,120]
        assert set(item) == {'slot','eligible_activities','eligible_durations'}
    assert options(setup, viewer='demo-daniella').json() == response.json()


def test_activity_specific_windows_do_not_grant_wrong_activity(setup):
    with connect() as connection:
        connection.execute('DELETE FROM social_windows')
    for user in ('demo-zaynah','demo-daniella'):
        create_social_window(window(f'{user}-coffee',user,['coffee'],'14:00','15:00'))
        create_social_window(window(f'{user}-walk',user,['walk'],'16:00','18:00'))
    result = [CandidateOption.model_validate(item) for item in options(setup).json()]
    assert [(item.eligible_activities,item.slot.duration_minutes,item.eligible_durations) for item in result] == [(['coffee'],60,[30,60]),(['walk'],120,[30,60,120])]


def test_both_busy_sets_subtracted_and_foreign_owner_ignored(setup):
    _, calendar, _ = setup
    calendar.busy = [BusyInterval(user_id='demo-zaynah',**span('14:30','15:00')),
                     BusyInterval(user_id='demo-daniella',**span('16:00','17:00')),
                     BusyInterval(user_id='demo-kusum',**span())]
    result = [CandidateOption.model_validate(item) for item in options(setup).json()]
    assert len(result) == 6
    assert sorted({item.slot.duration_minutes for item in result}) == [30,60]
    for item in result:
        assert max(item.eligible_durations) <= item.slot.duration_minutes


def test_both_hard_constraints_limit_choices(setup):
    user = get_user('demo-daniella')
    user.hard_constraints.allowed_activities = ['walk']
    user.hard_constraints.max_duration_minutes = 30
    save_user(user)
    result = options(setup).json()
    assert len(result) == 1
    assert result[0]['eligible_activities'] == ['walk']
    assert result[0]['eligible_durations'] == [30]


@pytest.mark.parametrize('audience', ['private','friends','selected_friends'])
def test_denied_windows_skip_calendar_lookup(setup, audience):
    _, calendar, _ = setup
    with connect() as connection:
        connection.execute('DELETE FROM social_windows WHERE user_id = ?',('demo-daniella',))
    create_social_window(window('restricted','demo-daniella',['coffee','walk'], audience=audience,
                                selected=['demo-zaynah'] if audience=='selected_friends' else []))
    assert options(setup).json() == []
    assert calendar.calls == []


def test_matching_only_selected_windows_and_removed_friendship(setup):
    _, calendar, _ = setup
    with connect() as connection:
        connection.execute('DELETE FROM social_windows')
    friend = create_friend_request('demo-zaynah','demo-daniella')
    respond_to_friend_request(friend.id,'demo-daniella','accept')
    create_social_window(window('a','demo-zaynah',['coffee'], audience='friends',mode='matching_only'))
    create_social_window(window('b','demo-daniella',['coffee'], audience='selected_friends',mode='matching_only',selected=['demo-zaynah']))
    assert len(options(setup).json()) == 1
    remove_friendship(friend.id,'demo-zaynah')
    calendar.calls.clear()
    assert options(setup).json() == []
    assert calendar.calls == []


@pytest.mark.parametrize('cause', ['no-overlap','too-short','no-activities','no-duration'])
def test_no_valid_options_skip_calendar(setup, cause):
    _, calendar, _ = setup
    if cause in ('no-overlap','too-short'):
        with connect() as connection:
            connection.execute('DELETE FROM social_windows WHERE user_id = ?',('demo-daniella',))
        create_social_window(window('new','demo-daniella',['coffee','walk'], '18:00' if cause=='no-overlap' else '14:00', '19:00' if cause=='no-overlap' else '14:15'))
    else:
        user = get_user('demo-daniella')
        if cause == 'no-activities':
            user.hard_constraints.allowed_activities = ['study']
        else:
            # Request uses only 60/120 while user permits at most 30.
            client, _, _ = setup
            record = client.post('/hangout-requests',headers={'X-Demo-User-Id':'demo-zaynah'},json={
                **span(), 'invitee_id':'demo-daniella','allowed_activities':['coffee'],'allowed_durations':[60,120],
            }).json()
            user.hard_constraints.max_duration_minutes = 30
            save_user(user)
            assert client.post(f"/hangout-requests/{record['id']}/candidates",headers={'X-Demo-User-Id':'demo-zaynah'}).json() == []
            assert calendar.calls == []
            return
        save_user(user)
    assert options(setup).json() == []
    assert calendar.calls == []


@pytest.mark.parametrize('failed_user',['demo-zaynah','demo-daniella'])
def test_calendar_failure_is_error_not_free_time(setup,failed_user):
    _, calendar, _ = setup
    calendar.fail_user = failed_user
    response = options(setup)
    assert response.status_code == 502
    assert 'SECRET' not in response.text


def test_fully_busy_returns_empty(setup):
    _, calendar, _ = setup
    calendar.busy = [BusyInterval(user_id='demo-daniella',**span())]
    assert options(setup).json() == []


def test_settings_and_windows_reloaded_after_calendar_wait(setup):
    _, calendar, _ = setup
    def change_settings(user_id):
        if user_id == 'demo-daniella':
            user = get_user('demo-daniella')
            user.hard_constraints.allowed_activities = ['study']
            save_user(user)
    calendar.on_read = change_settings
    assert options(setup).json() == []


def test_unauthorized_missing_and_unknown_identity_skip_calendar(setup):
    client, calendar, request_id = setup
    assert options(setup,viewer='demo-kusum').status_code == 404
    assert options(setup,viewer='demo-unknown').status_code == 401
    assert client.post(f'/hangout-requests/{request_id}/candidates').status_code == 401
    assert client.post('/hangout-requests/missing/candidates',headers={'X-Demo-User-Id':'demo-zaynah'}).status_code == 404
    assert calendar.calls == []


def test_friend_removal_during_calendar_wait_revokes_match(setup):
    _, calendar, _ = setup
    with connect() as connection:
        connection.execute('DELETE FROM social_windows')
    friend = create_friend_request('demo-zaynah','demo-daniella')
    respond_to_friend_request(friend.id,'demo-daniella','accept')
    for id,owner in [('a','demo-zaynah'),('b','demo-daniella')]:
        create_social_window(window(id,owner,['coffee'],audience='friends'))
    calendar.on_read = lambda user_id: remove_friendship(friend.id,'demo-zaynah')
    assert options(setup).json() == []


def test_request_clipping_offsets_and_touching_busy_boundaries(setup):
    client, calendar, _ = setup
    calendar.busy = [BusyInterval(user_id='demo-zaynah',**span('14:00','15:00')),
                     BusyInterval(user_id='demo-daniella',**span('16:00','18:00'))]
    request = client.post('/hangout-requests',headers={'X-Demo-User-Id':'demo-zaynah'},json={
        'start':'2026-10-18T19:00:00Z','end':'2026-10-18T20:00:00Z',
        'invitee_id':'demo-daniella','allowed_activities':['coffee'],'allowed_durations':[30,60],
    }).json()
    response = client.post(f"/hangout-requests/{request['id']}/candidates",headers={'X-Demo-User-Id':'demo-zaynah'})
    result = CandidateOption.model_validate(response.json()[0])
    assert result.slot.start.hour == 19
    assert result.slot.end.hour == 20
    assert result.eligible_durations == [30,60]
