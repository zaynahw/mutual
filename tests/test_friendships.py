"""Friendship lookup is symmetric and requires an accepted request."""
import sqlite3

import pytest
from pydantic import ValidationError

from backend.database import connect
from backend.friendships import are_friends, create_friend_request, list_friend_requests
from backend.seed import seed_demo_data


@pytest.fixture
def database(tmp_path, monkeypatch):
    monkeypatch.setenv('MUTUAL_DATABASE_PATH', str(tmp_path / 'friendships.db'))
    seed_demo_data()


@pytest.mark.parametrize('sender,recipient', [
    ('demo-zaynah', 'demo-daniella'), ('demo-daniella', 'demo-zaynah'),
])
@pytest.mark.parametrize('status', ['pending', 'accepted', 'declined'])
def test_only_accepted_pairs_match_both_lookup_orders(database, sender, recipient, status):
    responded_at = None if status == 'pending' else '2026-10-17T15:00:00Z'
    with connect() as connection:
        connection.execute(
            '''INSERT INTO friend_requests
               (id, sender_id, recipient_id, status, created_at, responded_at)
               VALUES (?, ?, ?, ?, ?, ?)''',
            ('friend-test', sender, recipient, status, '2026-10-17T14:00:00Z', responded_at),
        )
    assert are_friends(sender, recipient) is (status == 'accepted')
    assert are_friends(recipient, sender) is (status == 'accepted')
    assert are_friends(sender, 'demo-kusum') is False
    assert are_friends(sender, sender) is False


def test_empty_unknown_and_sql_like_ids_do_not_match(database):
    assert are_friends('demo-zaynah', 'demo-daniella') is False
    assert are_friends('demo-zaynah', 'demo-missing') is False
    assert are_friends("' OR 1=1 --", 'demo-zaynah') is False


def test_create_is_pending_and_visible_to_both_participants_only(database):
    request = create_friend_request('demo-zaynah', 'demo-daniella')
    assert request.id.startswith('friend-')
    assert request.status == 'pending'
    assert request.responded_at is None
    assert request.created_at.utcoffset().total_seconds() == 0
    assert list_friend_requests('demo-zaynah') == [request]
    assert list_friend_requests('demo-daniella') == [request]
    assert list_friend_requests('demo-kusum') == []
    assert are_friends('demo-zaynah', 'demo-daniella') is False


def test_list_includes_incoming_outgoing_in_stable_order(database):
    outgoing = create_friend_request('demo-zaynah', 'demo-daniella')
    incoming = create_friend_request('demo-mariann', 'demo-zaynah')
    create_friend_request('demo-kusum', 'demo-daniella')
    assert list_friend_requests('demo-zaynah') == sorted(
        [outgoing, incoming], key=lambda request: (request.created_at, request.id),
    )


@pytest.mark.parametrize('reverse', [False, True])
def test_create_rejects_duplicate_pending_pairs_without_overwriting(database, reverse):
    original = create_friend_request('demo-zaynah', 'demo-daniella')
    sender, recipient = ('demo-daniella', 'demo-zaynah') if reverse else ('demo-zaynah', 'demo-daniella')
    with pytest.raises(sqlite3.IntegrityError):
        create_friend_request(sender, recipient)
    assert list_friend_requests('demo-zaynah') == [original]


def test_self_request_fails_before_insert(database):
    with pytest.raises(ValidationError):
        create_friend_request('demo-zaynah', 'demo-zaynah')
    assert list_friend_requests('demo-zaynah') == []


@pytest.mark.parametrize('sender,recipient', [
    ('demo-missing', 'demo-zaynah'), ('demo-zaynah', 'demo-missing'),
])
def test_unknown_participant_fails_without_insert(database, sender, recipient):
    with pytest.raises(sqlite3.IntegrityError):
        create_friend_request(sender, recipient)
    assert list_friend_requests('demo-zaynah') == []


@pytest.mark.parametrize('status', ['accepted', 'declined'])
def test_answered_history_remains_listed_and_controls_new_requests(database, status):
    original = create_friend_request('demo-zaynah', 'demo-daniella')
    with connect() as connection:
        connection.execute(
            'UPDATE friend_requests SET status = ?, responded_at = ? WHERE id = ?',
            (status, original.created_at.isoformat(), original.id),
        )
    assert list_friend_requests('demo-zaynah')[0].status == status
    if status == 'accepted':
        with pytest.raises(sqlite3.IntegrityError):
            create_friend_request('demo-daniella', 'demo-zaynah')
    else:
        create_friend_request('demo-daniella', 'demo-zaynah')
        assert len(list_friend_requests('demo-zaynah')) == 2
