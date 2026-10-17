import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.repositories import list_social_windows
from backend.seed import seed_demo_data


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('MUTUAL_DATABASE_PATH', str(tmp_path / 'windows.db'))
    seed_demo_data()
    with TestClient(app) as client:
        yield client


def payload():
    return {
        'start': '2026-10-18T14:00:00-04:00', 'end': '2026-10-18T16:00:00-04:00',
        'allowed_activities': ['coffee', 'walk'],
        'visibility': {'audience': 'friends', 'selected_friend_ids': []},
        'sharing_mode': 'visible',
    }


@pytest.mark.parametrize('identity', ['demo-zaynah', 'demo-daniella', 'demo-kusum', 'demo-mariann'])
def test_list_is_owner_only(client, identity):
    response = client.get('/users/me/social-windows', headers={'X-Demo-User-Id': identity})
    assert response.status_code == 200
    assert response.json() == [window.model_dump(mode='json') for window in list_social_windows(identity)]


def test_create_assigns_owner_and_persists_without_leaking(client):
    headers = {'X-Demo-User-Id': 'demo-mariann'}
    response = client.post('/users/me/social-windows', json=payload(), headers=headers)
    assert response.status_code == 201
    record = response.json()
    assert record['user_id'] == 'demo-mariann'
    assert record['id'].startswith('window-')
    assert record in client.get('/users/me/social-windows', headers=headers).json()
    assert record not in client.get('/users/me/social-windows', headers={'X-Demo-User-Id': 'demo-kusum'}).json()
    second = client.post('/users/me/social-windows', json=payload(), headers=headers)
    assert second.json()['id'] != record['id']


@pytest.mark.parametrize('changes', [
    {'end': '2026-10-18T13:00:00-04:00'},
    {'start': '2026-10-18T14:00:00'},
    {'allowed_activities': []}, {'allowed_activities': ['dinner']},
    {'user_id': 'demo-zaynah'}, {'id': 'my-custom-id'},
])
def test_invalid_create_does_not_insert(client, changes):
    response = client.post('/users/me/social-windows', json=payload() | changes,
                           headers={'X-Demo-User-Id': 'demo-mariann'})
    assert response.status_code == 422
    assert list_social_windows('demo-mariann') == []


def test_selected_friends_rejects_non_friend(client):
    body = payload() | {'visibility': {'audience': 'selected_friends', 'selected_friend_ids': ['demo-zaynah']}}
    response = client.post('/users/me/social-windows', json=body, headers={'X-Demo-User-Id': 'demo-mariann'})
    assert response.status_code == 422
    assert list_social_windows('demo-mariann') == []


@pytest.mark.parametrize('method', ['get', 'post'])
@pytest.mark.parametrize('headers', [{}, {'X-Demo-User-Id': 'demo-unknown'}])
def test_identity_required(client, method, headers):
    kwargs = {'json': payload()} if method == 'post' else {}
    response = getattr(client, method)('/users/me/social-windows', headers=headers, **kwargs)
    assert response.status_code == 401


@pytest.mark.parametrize('audience', ['private', 'community', 'friends'])
def test_modes_and_audiences_persist(client, audience):
    body = payload() | {'visibility': {'audience': audience}, 'sharing_mode': 'matching_only'}
    response = client.post('/users/me/social-windows', json=body, headers={'X-Demo-User-Id': 'demo-mariann'})
    assert response.status_code == 201
    assert response.json()['visibility']['audience'] == audience
    assert response.json()['sharing_mode'] == 'matching_only'


def test_post_preflight(client):
    response = client.options('/users/me/social-windows', headers={
        'Origin': 'http://localhost:5173', 'Access-Control-Request-Method': 'POST',
        'Access-Control-Request-Headers': 'content-type,x-demo-user-id',
    })
    assert response.status_code == 200


def create_for_mariann(client):
    headers = {'X-Demo-User-Id': 'demo-mariann'}
    record = client.post('/users/me/social-windows', json=payload(), headers=headers).json()
    return headers, f"/users/me/social-windows/{record['id']}", record


def test_owner_edit_persists_same_id_and_owner(client):
    headers, path, record = create_for_mariann(client)
    body = payload() | {'allowed_activities': ['study'], 'sharing_mode': 'matching_only'}
    response = client.put(path, json=body, headers=headers)
    assert response.status_code == 200
    updated = response.json()
    assert updated['id'] == record['id']
    assert updated['user_id'] == record['user_id']
    assert updated['allowed_activities'] == ['study']
    assert updated in client.get('/users/me/social-windows', headers=headers).json()


def test_invalid_edit_keeps_original(client):
    headers, path, record = create_for_mariann(client)
    assert client.put(path, json=payload() | {'allowed_activities': []}, headers=headers).status_code == 422
    assert record in client.get('/users/me/social-windows', headers=headers).json()


@pytest.mark.parametrize('method', ['put', 'delete'])
def test_other_owner_and_missing_window_are_indistinguishable(client, method):
    headers, path, record = create_for_mariann(client)
    other = {'X-Demo-User-Id': 'demo-kusum'}
    kwargs = {'json': payload()} if method == 'put' else {}
    response = getattr(client, method)(path, headers=other, **kwargs)
    missing = getattr(client, method)('/users/me/social-windows/window-missing', headers=other, **kwargs)
    assert response.status_code == missing.status_code == 404
    assert response.json() == missing.json()
    assert record in client.get('/users/me/social-windows', headers=headers).json()


def test_delete_removes_only_target_and_has_no_body(client):
    headers, path, record = create_for_mariann(client)
    second = client.post('/users/me/social-windows', json=payload(), headers=headers).json()
    response = client.delete(path, headers=headers)
    assert response.status_code == 204
    assert response.content == b''
    assert client.get('/users/me/social-windows', headers=headers).json() == [second]
    assert client.delete(path, headers=headers).status_code == 404


@pytest.mark.parametrize('method', ['put', 'delete'])
@pytest.mark.parametrize('headers', [{}, {'X-Demo-User-Id': 'demo-unknown'}])
def test_edit_delete_require_identity(client, method, headers):
    kwargs = {'json': payload()} if method == 'put' else {}
    assert getattr(client, method)('/users/me/social-windows/window-1', headers=headers, **kwargs).status_code == 401


@pytest.mark.parametrize('field,value', [('id', 'override-id'), ('user_id', 'demo-zaynah')])
def test_edit_cannot_override_server_fields(client, field, value):
    headers, path, record = create_for_mariann(client)
    assert client.put(path, json=payload() | {field: value}, headers=headers).status_code == 422
    assert record in client.get('/users/me/social-windows', headers=headers).json()


def test_selected_friends_edit_requires_friendship_but_owner_can_delete_seeded_window(client):
    headers = {'X-Demo-User-Id': 'demo-zaynah'}
    body = payload() | {'visibility': {'audience': 'selected_friends', 'selected_friend_ids': ['demo-daniella']}}
    assert client.put('/users/me/social-windows/window-4', json=body, headers=headers).status_code == 422
    assert client.delete('/users/me/social-windows/window-4', headers=headers).status_code == 204


@pytest.mark.parametrize('method', ['PUT', 'DELETE'])
def test_edit_delete_cors(client, method):
    response = client.options('/users/me/social-windows/window-1', headers={
        'Origin': 'http://localhost:5173', 'Access-Control-Request-Method': method,
        'Access-Control-Request-Headers': 'content-type,x-demo-user-id',
    })
    assert response.status_code == 200


@pytest.mark.parametrize('method', ['post', 'put'])
@pytest.mark.parametrize('state', ['accepted', 'pending', 'declined', 'removed', 'unknown', 'self', 'mixed'])
def test_selected_audience_validates_every_relationship_on_create_and_edit(client, method, state):
    from backend.friendships import create_friend_request, respond_to_friend_request, remove_friendship

    headers = {'X-Demo-User-Id': 'demo-mariann'}
    original = client.post('/users/me/social-windows', json=payload(), headers=headers).json()
    selected = ['demo-zaynah']
    if state in ('accepted', 'pending', 'declined', 'removed', 'mixed'):
        request = create_friend_request('demo-mariann', 'demo-zaynah')
        if state != 'pending':
            respond_to_friend_request(request.id, 'demo-zaynah', 'decline' if state == 'declined' else 'accept')
        if state == 'removed':
            remove_friendship(request.id, 'demo-mariann')
        if state == 'mixed':
            selected.append('demo-kusum')
    elif state == 'unknown':
        selected = ['demo-missing']
    elif state == 'self':
        selected = ['demo-mariann']

    body = payload() | {'visibility': {'audience': 'selected_friends', 'selected_friend_ids': selected}}
    path = '/users/me/social-windows' + (f"/{original['id']}" if method == 'put' else '')
    response = getattr(client, method)(path, json=body, headers=headers)
    if state == 'accepted':
        assert response.status_code == (201 if method == 'post' else 200)
        assert response.json()['visibility']['selected_friend_ids'] == selected
        assert response.json() in client.get('/users/me/social-windows', headers=headers).json()
    else:
        assert response.status_code == 422
        assert client.get('/users/me/social-windows', headers=headers).json() == [original]


def test_removed_friend_stays_in_old_window_but_cannot_access_it(client):
    from backend.friendships import create_friend_request, respond_to_friend_request, remove_friendship
    from backend.models import VisibilityPolicy
    from backend.repositories import get_user
    from backend.services.permissions import can_access

    headers = {'X-Demo-User-Id': 'demo-mariann'}
    request = create_friend_request('demo-mariann', 'demo-zaynah')
    respond_to_friend_request(request.id, 'demo-zaynah', 'accept')
    body = payload() | {'visibility': {'audience': 'selected_friends', 'selected_friend_ids': ['demo-zaynah']}}
    saved = client.post('/users/me/social-windows', json=body, headers=headers).json()
    remove_friendship(request.id, 'demo-zaynah')
    assert saved in client.get('/users/me/social-windows', headers=headers).json()
    assert not can_access(get_user('demo-mariann'), get_user('demo-zaynah'), VisibilityPolicy.model_validate(saved['visibility']))
    # Owner can clear stale selections by changing the audience.
    assert client.put(f"/users/me/social-windows/{saved['id']}", json=payload(), headers=headers).status_code == 200
