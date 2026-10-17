import sqlite3

import pytest
from fastapi.testclient import TestClient

from backend.database import FRIEND_REQUESTS_TABLE, connect, initialize_database
from backend.friendships import (
    are_friends, create_friend_request, list_friend_requests,
    remove_friendship, respond_to_friend_request,
)
from backend.main import app


def accepted():
    request = create_friend_request('demo-zaynah', 'demo-daniella')
    return respond_to_friend_request(request.id, 'demo-daniella', 'accept')


@pytest.mark.parametrize('actor', ['demo-zaynah', 'demo-daniella'])
def test_either_participant_removes_and_readds_without_old_replay_affecting_new(seeded_database, actor):
    first = accepted()
    removed = remove_friendship(first.id, actor)
    assert removed.status == 'removed'
    assert removed.responded_at == first.responded_at
    assert not are_friends(first.sender_id, first.recipient_id)
    assert remove_friendship(first.id, actor) == removed
    newer = accepted()
    assert remove_friendship(first.id, actor) == removed
    assert are_friends(first.sender_id, first.recipient_id)
    assert [record.status for record in list_friend_requests(actor)] == ['removed', 'accepted']
    assert newer.id != first.id


def test_outsider_cannot_remove_and_removed_record_cannot_reopen(seeded_database):
    request = accepted()
    with pytest.raises(PermissionError):
        remove_friendship(request.id, 'demo-kusum')
    assert are_friends(request.sender_id, request.recipient_id)
    remove_friendship(request.id, request.sender_id)
    with pytest.raises(PermissionError):
        remove_friendship(request.id, 'demo-kusum')
    with pytest.raises(ValueError):
        respond_to_friend_request(request.id, request.recipient_id, 'accept')


@pytest.mark.parametrize('status', ['pending', 'declined'])
def test_cannot_remove_non_friendship(seeded_database, status):
    request = create_friend_request('demo-zaynah', 'demo-daniella')
    if status == 'declined':
        respond_to_friend_request(request.id, request.recipient_id, 'decline')
    with pytest.raises(ValueError):
        remove_friendship(request.id, request.sender_id)
    assert list_friend_requests(request.sender_id)[0].status == status


def test_old_schema_upgrade_preserves_records_and_index(seeded_database):
    # Recreate the original schema to exercise the actual upgrade path.
    with connect() as connection:
        connection.execute('DROP TABLE friend_requests')
        connection.execute(FRIEND_REQUESTS_TABLE.replace(", 'removed'", ''))
    first = accepted()
    with connect() as connection:
        before = [dict(row) for row in connection.execute('SELECT * FROM friend_requests')]
    initialize_database()
    initialize_database()
    with connect() as connection:
        assert [dict(row) for row in connection.execute('SELECT * FROM friend_requests')] == before
        assert connection.execute('PRAGMA foreign_key_check').fetchall() == []
    with pytest.raises(sqlite3.IntegrityError):
        create_friend_request('demo-daniella', 'demo-zaynah')
    assert remove_friendship(first.id, first.sender_id).status == 'removed'
    assert len(list_friend_requests(first.sender_id)) == 1


def test_migration_failure_rolls_back_original_table(seeded_database):
    with connect() as connection:
        connection.execute('DROP TABLE friend_requests')
        connection.execute(FRIEND_REQUESTS_TABLE.replace(", 'removed'", ''))
    first = accepted()
    # Force a failure after rebuilding, when the index is recreated.
    with connect() as connection:
        connection.execute('CREATE TABLE unique_active_friend_pair (id TEXT)')
    with pytest.raises(sqlite3.OperationalError):
        initialize_database()
    with connect() as connection:
        sql = connection.execute("SELECT sql FROM sqlite_master WHERE name='friend_requests'").fetchone()[0]
        assert "'removed'" not in sql
        assert connection.execute("SELECT name FROM sqlite_master WHERE name='friend_requests_upgrade'").fetchone() is None
    assert list_friend_requests(first.sender_id) == [first]


def test_removal_route_and_readd_flow(seeded_database):
    first = accepted()
    with TestClient(app) as client:
        path = f'/friend-requests/{first.id}/remove'
        assert client.post(path).status_code == 401
        assert client.post(path, headers={'X-Demo-User-Id':'demo-kusum'}).status_code == 403
        headers = {'X-Demo-User-Id': first.sender_id}
        response = client.post(path, headers=headers)
        assert response.status_code == 200
        assert response.json()['status'] == 'removed'
        assert client.post(path, headers=headers).json() == response.json()
        assert client.post('/friend-requests/missing/remove', headers=headers).status_code == 404
        new = client.post('/friend-requests', headers=headers, json={'recipient_id': first.recipient_id})
        assert new.status_code == 201
        assert client.post(f"/friend-requests/{new.json()['id']}/remove", headers=headers).status_code == 409
