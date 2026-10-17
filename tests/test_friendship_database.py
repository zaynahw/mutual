"""Friendship table constraints, independent of future API/service logic."""
import sqlite3

import pytest

from backend.database import connect, initialize_database
from backend.models import FriendRequest
from backend.seed import seed_demo_data


@pytest.fixture
def database(tmp_path, monkeypatch):
    monkeypatch.setenv('MUTUAL_DATABASE_PATH', str(tmp_path / 'friends.db'))
    seed_demo_data()


def insert_request(request_id='friend-1', sender='demo-zaynah', recipient='demo-daniella',
                   status='pending', responded_at=None):
    with connect() as connection:
        connection.execute(
            '''INSERT INTO friend_requests
               (id, sender_id, recipient_id, status, created_at, responded_at)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (request_id, sender, recipient, status, '2026-10-17T14:00:00Z', responded_at),
        )


def test_friend_record_survives_reinitialization(database):
    insert_request()
    initialize_database()
    with connect() as connection:
        row = connection.execute('SELECT * FROM friend_requests').fetchone()
    record = FriendRequest.model_validate(dict(row))
    assert record.sender_id == 'demo-zaynah'
    assert record.status == 'pending'


@pytest.mark.parametrize('status,responded_at', [('pending', None), ('accepted', '2026-10-17T15:00:00Z')])
@pytest.mark.parametrize('reverse', [False, True])
def test_active_pair_blocks_both_directions(database, status, responded_at, reverse):
    insert_request(status=status, responded_at=responded_at)
    sender, recipient = ('demo-daniella', 'demo-zaynah') if reverse else ('demo-zaynah', 'demo-daniella')
    with pytest.raises(sqlite3.IntegrityError):
        insert_request('friend-2', sender=sender, recipient=recipient)


def test_decline_allows_new_request_and_keeps_history(database):
    insert_request(status='declined', responded_at='2026-10-17T15:00:00Z')
    insert_request('friend-2', sender='demo-daniella', recipient='demo-zaynah')
    with connect() as connection:
        assert connection.execute('SELECT COUNT(*) FROM friend_requests').fetchone()[0] == 2


@pytest.mark.parametrize('changes', [
    {'recipient': 'demo-zaynah'}, {'recipient': 'demo-missing'},
    {'sender': 'demo-missing'}, {'status': 'invalid'},
    {'status': 'accepted'}, {'status': 'declined'},
    {'responded_at': '2026-10-17T15:00:00Z'},
])
def test_invalid_relationship_state_rejected(database, changes):
    with pytest.raises(sqlite3.IntegrityError):
        insert_request(**changes)


def test_existing_users_and_windows_survive_schema_setup(database):
    initialize_database()
    with connect() as connection:
        assert connection.execute('SELECT COUNT(*) FROM users').fetchone()[0] == 4
        assert connection.execute('SELECT COUNT(*) FROM social_windows').fetchone()[0] == 5
        assert connection.execute('SELECT COUNT(*) FROM friend_requests').fetchone()[0] == 0
