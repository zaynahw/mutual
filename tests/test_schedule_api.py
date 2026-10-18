from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from backend.dependencies import get_calendar_adapter
from backend.friendships import create_friend_request, remove_friendship, respond_to_friend_request
from backend.main import app
from backend.models import BusyInterval, SocialWindow, VisibilityPolicy
from backend.repositories import create_social_window, get_user, save_user


class FakeCalendar:
    def __init__(self):
        self.calls = []
        self.fail = False
        self.on_read = None

    async def get_busy(self, user_id, search):
        self.calls.append(user_id)
        if self.fail:
            raise RuntimeError('SECRET CALENDAR CONTENT')
        if self.on_read:
            self.on_read()
        return [
            BusyInterval(user_id=user_id, start='2026-10-18T14:00:00-04:00', end='2026-10-18T17:00:00-04:00'),
            BusyInterval(user_id='demo-kusum', start='2026-10-18T15:00:00-04:00', end='2026-10-18T16:00:00-04:00'),
        ]


@pytest.fixture
def setup(seeded_database):
    for window_id, mode in [('private-window', 'visible'), ('hidden-window', 'matching_only')]:
        create_social_window(SocialWindow(
            id=window_id, user_id='demo-zaynah', start='2026-10-18T14:00:00-04:00',
            end='2026-10-18T18:00:00-04:00', allowed_activities=['coffee'],
            visibility=VisibilityPolicy(audience='private' if mode == 'visible' else 'community'), sharing_mode=mode,
        ))
    adapter = FakeCalendar()
    app.dependency_overrides[get_calendar_adapter] = lambda: adapter
    try:
        with TestClient(app) as client:
            yield client, adapter
    finally:
        app.dependency_overrides.pop(get_calendar_adapter, None)


def view(client, viewer='demo-daniella', owner='demo-zaynah', start='2026-10-18T00:00:00-04:00', end='2026-10-19T00:00:00-04:00'):
    return client.get(f'/users/{owner}/schedule', params={'start':start, 'end':end}, headers={'X-Demo-User-Id': viewer})


def befriend(a='demo-zaynah', b='demo-daniella'):
    request = create_friend_request(a, b)
    respond_to_friend_request(request.id, b, 'accept')
    return request


def ids(response):
    return {window['id'] for window in response.json()['social_windows']}


def test_community_view_has_no_private_fields_or_calendar_call(setup):
    client, calendar = setup
    response = view(client)
    assert response.status_code == 200
    assert ids(response) == {'window-3'}
    assert response.json()['calendar_busy'] is None
    assert calendar.calls == []
    assert set(response.json()['user']) == {'id','display_name','is_demo','community'}
    for window in response.json()['social_windows']:
        assert set(window) == {'id','start','end','allowed_activities'}


def test_friends_selected_friends_and_removal_revoke_access(setup):
    client, calendar = setup
    friend = befriend()
    assert ids(view(client)) == {'window-1','window-3','window-4'}
    assert view(client).json()['calendar_busy'] is not None
    befriend(b='demo-kusum')
    assert ids(view(client, viewer='demo-kusum')) == {'window-1','window-3'}
    remove_friendship(friend.id, friend.sender_id)
    calendar.calls.clear()
    response = view(client)
    assert ids(response) == {'window-3'}
    assert response.json()['calendar_busy'] is None
    assert calendar.calls == []


def test_owner_sees_private_and_matching_only_windows(setup):
    client, _ = setup
    assert ids(view(client, viewer='demo-zaynah')) == {'window-1','window-3','window-4','private-window','hidden-window'}


def test_intervals_clipped_to_range_and_other_users_busy_ignored(setup):
    client, _ = setup
    befriend()
    response = view(client, start='2026-10-18T15:00:00-04:00', end='2026-10-18T16:00:00-04:00')
    data = response.json()
    assert ids(response) == {'window-1'}
    for item in [*data['social_windows'], *data['calendar_busy']]:
        assert datetime.fromisoformat(item['start']) == datetime(2026,10,18,19,tzinfo=timezone.utc)
        assert datetime.fromisoformat(item['end']) == datetime(2026,10,18,20,tzinfo=timezone.utc)
    assert len(data['calendar_busy']) == 1


def test_no_overlap_and_calendar_null_vs_empty(setup):
    client, _ = setup
    response = view(client, start='2026-10-18T21:00:00-04:00', end='2026-10-18T22:00:00-04:00')
    assert response.json()['social_windows'] == []
    assert response.json()['calendar_busy'] is None
    befriend()
    assert view(client, start='2026-10-18T21:00:00-04:00', end='2026-10-18T22:00:00-04:00').json()['calendar_busy'] == []


@pytest.mark.parametrize('start,end', [
    ('2026-10-18T14:00:00','2026-10-18T16:00:00Z'),
    ('2026-10-18T16:00:00Z','2026-10-18T14:00:00Z'),
    ('2026-10-18T14:00:00Z','2026-10-18T14:00:00Z'),
    ('bad','2026-10-18T16:00:00Z'),
])
def test_bad_ranges_return_422(setup, start, end):
    client, _ = setup
    assert view(client, start=start, end=end).status_code == 422


def test_identity_missing_owner_and_required_queries(setup):
    client, _ = setup
    assert client.get('/users/demo-zaynah/schedule').status_code == 401
    assert view(client, viewer='demo-missing').status_code == 401
    assert view(client, owner='demo-missing').status_code == 404
    assert client.get('/users/demo-zaynah/schedule', headers={'X-Demo-User-Id':'demo-zaynah'}).status_code == 422


def test_adapter_failure_is_generic_and_hidden_calendar_not_requested(setup):
    client, calendar = setup
    calendar.fail = True
    assert view(client).status_code == 200
    assert calendar.calls == []
    befriend()
    response = view(client)
    assert response.status_code == 502
    assert 'SECRET' not in response.text


def test_removed_during_calendar_read_is_filtered_before_response(setup):
    client, calendar = setup
    friend = befriend()
    calendar.on_read = lambda: remove_friendship(friend.id, friend.sender_id)
    response = view(client)
    assert response.json()['calendar_busy'] is None
    assert ids(response) == {'window-3'}


@pytest.mark.parametrize('audience', ['private', 'community', 'selected_friends'])
def test_calendar_policy_is_independent_of_social_windows(setup, audience):
    client, _ = setup
    owner = get_user('demo-zaynah')
    owner.calendar_sharing = VisibilityPolicy(audience=audience, selected_friend_ids=['demo-daniella'] if audience == 'selected_friends' else [])
    save_user(owner)
    if audience == 'selected_friends':
        befriend()
    response = view(client)
    assert (response.json()['calendar_busy'] is not None) is (audience != 'private')


def test_default_dependency_returns_fixture_mock_busy_blocks(setup):
    client, _ = setup
    app.dependency_overrides.pop(get_calendar_adapter)
    response = view(client, viewer='demo-zaynah')
    assert response.status_code == 200
    busy = response.json()['calendar_busy']
    assert len(busy) == 1
    assert datetime.fromisoformat(busy[0]['start']) == datetime.fromisoformat('2026-10-18T16:00:00-04:00')
    assert set(busy[0]) == {'start','end'}


def test_selected_calendar_excludes_non_selected_accepted_friend(setup):
    client, calendar = setup
    owner = get_user('demo-zaynah')
    owner.calendar_sharing = VisibilityPolicy(audience='selected_friends', selected_friend_ids=['demo-daniella'])
    save_user(owner)
    befriend(b='demo-kusum')
    assert view(client, viewer='demo-kusum').json()['calendar_busy'] is None
    assert calendar.calls == []


def test_owner_calendar_access_even_when_private(setup):
    client, _ = setup
    owner = get_user('demo-zaynah')
    owner.calendar_sharing = VisibilityPolicy(audience='private')
    save_user(owner)
    assert view(client, viewer=owner.id).json()['calendar_busy'] is not None
