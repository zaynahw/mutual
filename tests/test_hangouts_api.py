import json

import pytest

from backend.hangouts import get_hangout_request, list_hangout_requests
from backend.seed import DEFAULT_FIXTURE_PATH


def headers(user='zaynah'):
    return {'X-Demo-User-Id': f'demo-{user}'}


def payload():
    return json.loads(DEFAULT_FIXTURE_PATH.read_text())['frontend_examples']['create_request']


def test_create_persist_and_participant_retrieval(client):
    response = client.post('/hangout-requests', headers=headers(), json=payload())
    assert response.status_code == 201
    record = response.json()
    assert record['id'].startswith('request-')
    assert record['requester_id'] == 'demo-zaynah'
    assert record['invitee_id'] == 'demo-daniella'
    assert get_hangout_request(record['id']).model_dump(mode='json') == record
    for user in ('zaynah','daniella'):
        assert client.get(f"/hangout-requests/{record['id']}", headers=headers(user)).json() == record
        assert client.get('/hangout-requests', headers=headers(user)).json() == [record]
    # No friendship is needed to store intention; no availability is exposed.
    assert client.get('/hangout-requests', headers=headers('kusum')).json() == []
    assert client.get(f"/hangout-requests/{record['id']}", headers=headers('kusum')).status_code == 404


def test_missing_and_non_owned_requests_match_and_query_cannot_override_identity(client):
    record = client.post('/hangout-requests', headers=headers(), json=payload()).json()
    outsider = client.get(f"/hangout-requests/{record['id']}", headers=headers('kusum'))
    missing = client.get('/hangout-requests/missing', headers=headers('kusum'))
    assert outsider.status_code == missing.status_code == 404
    assert outsider.json() == missing.json()
    assert client.get('/hangout-requests?user_id=demo-zaynah', headers=headers('kusum')).json() == []


@pytest.mark.parametrize('changes,status', [
    ({'invitee_id':'demo-zaynah'},422), ({'invitee_id':'demo-missing'},404),
    ({'requester_id':'demo-kusum'},422), ({'id':'override'},422),
    ({'allowed_activities':[]},422), ({'allowed_activities':['dinner']},422),
    ({'allowed_durations':[45]},422), ({'allowed_durations':[True]},422),
    ({'start':'2026-10-18T14:00:00'},422),
    ({'end':'2026-10-18T13:00:00-04:00'},422),
    ({'end':'2026-10-18T14:15:00-04:00'},422),
])
def test_invalid_request_does_not_insert(client, changes, status):
    response = client.post('/hangout-requests', headers=headers(), json=payload() | changes)
    assert response.status_code == status
    assert list_hangout_requests('demo-zaynah') == []


@pytest.mark.parametrize('method,path', [
    ('post','/hangout-requests'), ('get','/hangout-requests'), ('get','/hangout-requests/missing'),
])
@pytest.mark.parametrize('identity', [None,'demo-unknown'])
def test_routes_require_identity(client, method, path, identity):
    request_headers = {} if identity is None else {'X-Demo-User-Id': identity}
    kwargs = {'json':payload()} if method == 'post' else {}
    assert getattr(client, method)(path, headers=request_headers, **kwargs).status_code == 401


def test_multiple_requests_same_pair_get_unique_ids(client):
    first = client.post('/hangout-requests', headers=headers(), json=payload())
    second = client.post('/hangout-requests', headers=headers(), json=payload())
    assert first.status_code == second.status_code == 201
    assert first.json()['id'] != second.json()['id']
    assert len(client.get('/hangout-requests', headers=headers()).json()) == 2
