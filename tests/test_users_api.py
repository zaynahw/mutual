"""Database-backed routes using the real demo identity dependency."""
import pytest

from backend.repositories import get_user, save_user


def test_directory_projects_only_public_fields(client):
    response = client.get('/users', headers={'X-Demo-User-Id': 'demo-zaynah'})
    assert response.status_code == 200
    records = response.json()
    assert len(records) == 4
    for record in records:
        assert set(record) == {'id', 'display_name', 'is_demo', 'community'}


@pytest.mark.parametrize('identity', ['demo-zaynah', 'demo-daniella', 'demo-kusum', 'demo-mariann'])
def test_me_returns_selected_owner_from_database(client, identity):
    response = client.get('/users/me', headers={'X-Demo-User-Id': identity})
    assert response.status_code == 200
    assert response.json() == get_user(identity).model_dump(mode='json')


@pytest.mark.parametrize('path', ['/users', '/users/me'])
@pytest.mark.parametrize('identity', [None, 'demo-unknown', ''])
def test_missing_or_unknown_identity_is_rejected(client, path, identity):
    headers = {} if identity is None else {'X-Demo-User-Id': identity}
    assert client.get(path, headers=headers).status_code == 401


def test_me_uses_header_not_query_identity_and_reads_updates(client):
    user = get_user('demo-zaynah')
    user.display_name = 'Zaynah updated (demo)'
    save_user(user)
    response = client.get('/users/me?user_id=demo-daniella', headers={'X-Demo-User-Id': user.id})
    assert response.json()['id'] == user.id
    assert response.json()['display_name'] == user.display_name


def test_health_is_public(client):
    assert client.get('/health').json() == {'status': 'ok'}


def test_browser_preflight_allows_demo_identity_header(client):
    response = client.options('/users', headers={
        'Origin': 'http://localhost:5173',
        'Access-Control-Request-Method': 'GET',
        'Access-Control-Request-Headers': 'X-Demo-User-Id',
    })
    assert response.status_code == 200
    assert response.headers['access-control-allow-origin'] == 'http://localhost:5173'
