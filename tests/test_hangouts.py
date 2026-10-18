import sqlite3

import pytest
from pydantic import ValidationError

from backend.database import connect, initialize_database
from backend.hangouts import create_hangout_request, get_hangout_request, list_hangout_requests
from backend.models import HangoutRequest


def test_round_trip_preserves_fields_and_reinitialization(request_record):
    create_hangout_request(request_record)
    initialize_database()
    assert get_hangout_request(request_record.id) == request_record
    assert list_hangout_requests(request_record.requester_id) == [request_record]
    assert list_hangout_requests(request_record.invitee_id) == [request_record]


def test_empty_missing_and_sql_like_values(request_record):
    assert get_hangout_request('missing') is None
    assert list_hangout_requests('demo-zaynah') == []
    create_hangout_request(request_record)
    assert get_hangout_request("' OR 1=1 --") is None
    assert list_hangout_requests("' OR 1=1 --") == []


def test_list_filters_both_roles_and_sorts_by_id(request_record):
    outgoing = HangoutRequest.model_validate(request_record.model_dump() | {'id': 'request-b'})
    incoming = HangoutRequest.model_validate(request_record.model_dump() | {
        'id': 'request-a', 'requester_id': 'demo-mariann', 'invitee_id': 'demo-zaynah',
    })
    unrelated = HangoutRequest.model_validate(request_record.model_dump() | {
        'id': 'request-c', 'requester_id': 'demo-kusum', 'invitee_id': 'demo-daniella',
    })
    for record in (outgoing, incoming, unrelated):
        create_hangout_request(record)
    assert list_hangout_requests('demo-zaynah') == [incoming, outgoing]
    assert list_hangout_requests('demo-kusum') == [unrelated]


def test_duplicate_rejected_without_overwriting(request_record):
    create_hangout_request(request_record)
    changed = HangoutRequest.model_validate(request_record.model_dump() | {'location': 'Changed location'})
    with pytest.raises(sqlite3.IntegrityError):
        create_hangout_request(changed)
    assert get_hangout_request(request_record.id) == request_record


@pytest.mark.parametrize('column', ['requester_id', 'invitee_id'])
def test_unknown_participants_rejected_without_partial_insert(request_record, column):
    changed = HangoutRequest.model_validate(request_record.model_dump() | {column: 'demo-missing'})
    with pytest.raises(sqlite3.IntegrityError):
        create_hangout_request(changed)
    assert get_hangout_request(changed.id) is None


def test_retrieval_revalidates_saved_data(request_record):
    create_hangout_request(request_record)
    with connect() as connection:
        connection.execute('UPDATE hangout_requests SET data = ? WHERE id = ?', ('{}', request_record.id))
    with pytest.raises(ValidationError):
        get_hangout_request(request_record.id)
    with pytest.raises(ValidationError):
        list_hangout_requests(request_record.requester_id)
