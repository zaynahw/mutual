"""Exercise the real HTTP -> identity -> friendship -> SQLite flow."""
import pytest
from fastapi.testclient import TestClient

from backend.friendships import are_friends
from backend.main import app
from backend.seed import seed_demo_data


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('MUTUAL_DATABASE_PATH', str(tmp_path / 'friend-api.db'))
    seed_demo_data()
    with TestClient(app) as client:
        yield client


def headers(user='zaynah'):
    return {'X-Demo-User-Id': f'demo-{user}'}


def send(client, sender='zaynah', recipient='daniella'):
    return client.post('/friend-requests', headers=headers(sender), json={'recipient_id': f'demo-{recipient}'})


def answer(client, request_id, decision='accept', user='daniella'):
    return client.post(f'/friend-requests/{request_id}/respond', headers=headers(user), json={'decision': decision})


def test_full_accept_flow_and_filtered_history(client):
    sent = send(client)
    assert sent.status_code == 201
    record = sent.json()
    assert record['sender_id'] == 'demo-zaynah'
    assert record['status'] == 'pending'
    assert record['responded_at'] is None
    assert are_friends('demo-zaynah', 'demo-daniella') is False
    for user in ('zaynah', 'daniella'):
        assert client.get('/friend-requests', headers=headers(user)).json() == [record]
    assert client.get('/friend-requests?user_id=demo-zaynah', headers=headers('kusum')).json() == []
    response = answer(client, record['id'])
    assert response.status_code == 200
    assert response.json()['status'] == 'accepted'
    assert response.json()['responded_at'] is not None
    assert are_friends('demo-daniella', 'demo-zaynah') is True
    assert answer(client, record['id']).json() == response.json()
    assert send(client, 'daniella', 'zaynah').status_code == 409


def test_decline_retry_and_finalized_conflict(client):
    record = send(client).json()
    declined = answer(client, record['id'], 'decline')
    assert declined.status_code == 200
    assert answer(client, record['id'], 'decline').json() == declined.json()
    assert answer(client, record['id'], 'accept').status_code == 409
    assert are_friends('demo-zaynah', 'demo-daniella') is False
    assert send(client, 'daniella', 'zaynah').status_code == 201


@pytest.mark.parametrize('actor', ['zaynah', 'kusum'])
def test_only_recipient_may_answer(client, actor):
    record = send(client).json()
    assert answer(client, record['id'], user=actor).status_code == 403
    assert client.get('/friend-requests', headers=headers()).json() == [record]


@pytest.mark.parametrize('reverse', [False, True])
def test_duplicate_pending_returns_409_without_extra_records(client, reverse):
    original = send(client).json()
    duplicate = send(client, 'daniella', 'zaynah') if reverse else send(client)
    assert duplicate.status_code == 409
    assert client.get('/friend-requests', headers=headers()).json() == [original]


@pytest.mark.parametrize('body,status', [
    ({'recipient_id': 'demo-zaynah'}, 422),
    ({'recipient_id': 'demo-missing'}, 404),
    ({'recipient_id': 'not-a-demo-id'}, 422),
    ({'recipient_id': 'demo-daniella', 'sender_id': 'demo-kusum'}, 422),
])
def test_invalid_create_inputs(client, body, status):
    assert client.post('/friend-requests', headers=headers(), json=body).status_code == status
    assert client.get('/friend-requests', headers=headers()).json() == []


def test_missing_request_and_invalid_response_input(client):
    assert answer(client, 'missing').status_code == 404
    record = send(client).json()
    assert answer(client, record['id'], 'maybe').status_code == 422
    response = client.post(f"/friend-requests/{record['id']}/respond", headers=headers('kusum'),
                           json={'decision': 'accept', 'recipient_id': 'demo-daniella'})
    assert response.status_code == 422
    assert client.get('/friend-requests', headers=headers()).json() == [record]


@pytest.mark.parametrize('identity', [None, 'demo-unknown'])
@pytest.mark.parametrize('method,path,body', [
    ('get', '/friend-requests', None),
    ('post', '/friend-requests', {'recipient_id': 'demo-daniella'}),
    ('post', '/friend-requests/missing/respond', {'decision': 'accept'}),
])
def test_identity_required(client, identity, method, path, body):
    request_headers = {} if identity is None else {'X-Demo-User-Id': identity}
    kwargs = {} if body is None else {'json': body}
    assert getattr(client, method)(path, headers=request_headers, **kwargs).status_code == 401
