"""Initial hangout storage constraints; no request routes are implemented yet."""
import sqlite3

import pytest

from backend.database import connect, initialize_database
from backend.friendships import create_friend_request, list_friend_requests
from backend.models import HangoutRequest


def insert(request):
    with connect() as connection:
        connection.execute(
            '''INSERT INTO hangout_requests (id, requester_id, invitee_id, data)
               VALUES (?, ?, ?, ?)''',
            (request.id, request.requester_id, request.invitee_id, request.model_dump_json()),
        )


def test_request_json_survives_connections_and_reinitialization(request_record):
    insert(request_record)
    initialize_database()
    with connect() as connection:
        row = connection.execute('SELECT * FROM hangout_requests WHERE id = ?', (request_record.id,)).fetchone()
    restored = HangoutRequest.model_validate_json(row['data'])
    assert restored == request_record
    assert row['requester_id'] == restored.requester_id
    assert row['invitee_id'] == restored.invitee_id


@pytest.mark.parametrize('column', ['requester_id', 'invitee_id'])
def test_unknown_participant_rejected_by_sql(request_record, column):
    changed = HangoutRequest.model_validate(request_record.model_dump() | {column: 'demo-missing'})
    with pytest.raises(sqlite3.IntegrityError):
        insert(changed)


def test_self_request_rejected_by_sql_independently_of_pydantic(request_record):
    with pytest.raises(sqlite3.IntegrityError):
        with connect() as connection:
            connection.execute(
                'INSERT INTO hangout_requests (id, requester_id, invitee_id, data) VALUES (?, ?, ?, ?)',
                (request_record.id, request_record.requester_id, request_record.requester_id, request_record.model_dump_json()),
            )


def test_duplicate_id_rejected_but_multiple_requests_between_pair_allowed(request_record):
    insert(request_record)
    with pytest.raises(sqlite3.IntegrityError):
        insert(request_record)
    another = HangoutRequest.model_validate(request_record.model_dump() | {'id': 'request-another'})
    insert(another)
    with connect() as connection:
        assert connection.execute('SELECT COUNT(*) FROM hangout_requests').fetchone()[0] == 2


def test_schema_setup_preserves_users_windows_and_friend_requests(request_record):
    friend = create_friend_request(request_record.requester_id, request_record.invitee_id)
    initialize_database()
    with connect() as connection:
        assert connection.execute('SELECT COUNT(*) FROM users').fetchone()[0] == 4
        assert connection.execute('SELECT COUNT(*) FROM social_windows').fetchone()[0] == 5
        assert connection.execute('SELECT COUNT(*) FROM hangout_requests').fetchone()[0] == 0
    assert list_friend_requests(friend.sender_id) == [friend]
