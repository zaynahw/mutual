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


def test_selected_friends_is_explicitly_deferred(client):
    body = payload() | {'visibility': {'audience': 'selected_friends', 'selected_friend_ids': ['demo-zaynah']}}
    response = client.post('/users/me/social-windows', json=body, headers={'X-Demo-User-Id': 'demo-mariann'})
    assert response.status_code == 409
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


def test_selected_friends_edit_deferred_but_owner_can_delete_seeded_window(client):
    headers = {'X-Demo-User-Id': 'demo-zaynah'}
    body = payload() | {'visibility': {'audience': 'selected_friends', 'selected_friend_ids': ['demo-daniella']}}
    assert client.put('/users/me/social-windows/window-4', json=body, headers=headers).status_code == 409
    assert client.delete('/users/me/social-windows/window-4', headers=headers).status_code == 204


@pytest.mark.parametrize('method', ['PUT', 'DELETE'])
def test_edit_delete_cors(client, method):
    response = client.options('/users/me/social-windows/window-1', headers={
        'Origin': 'http://localhost:5173', 'Access-Control-Request-Method': method,
        'Access-Control-Request-Headers': 'content-type,x-demo-user-id',
    })
    assert response.status_code == 200
