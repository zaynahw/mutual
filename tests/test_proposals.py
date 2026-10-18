"""Proposal storage; plan validation and HTTP authorization are separate layers."""
import json
import sqlite3

import pytest
from pydantic import ValidationError

from backend.database import connect, initialize_database
from backend.hangouts import create_hangout_request, get_hangout_request
from backend.models import HangoutRequest, Proposal
from backend.proposals import create_proposal, get_proposal, list_proposals_for_request
from backend.seed import DEFAULT_FIXTURE_PATH


@pytest.fixture
def proposal_record(request_record):
    create_hangout_request(request_record)
    return Proposal.model_validate(json.loads(DEFAULT_FIXTURE_PATH.read_text())['proposal'])


def test_proposal_round_trip_and_reinitialization(proposal_record):
    create_proposal(proposal_record)
    initialize_database()
    assert get_proposal(proposal_record.id) == proposal_record
    assert list_proposals_for_request(proposal_record.request_id) == [proposal_record]
    assert get_hangout_request(proposal_record.request_id) is not None


def test_missing_and_sql_like_queries(proposal_record):
    assert get_proposal('missing') is None
    assert list_proposals_for_request(proposal_record.request_id) == []
    create_proposal(proposal_record)
    assert get_proposal("' OR 1=1 --") is None
    assert list_proposals_for_request("' OR 1=1 --") == []


def test_duplicate_id_cannot_overwrite(proposal_record):
    create_proposal(proposal_record)
    changed = Proposal.model_validate(proposal_record.model_dump() | {'location':'Changed location'})
    with pytest.raises(sqlite3.IntegrityError):
        create_proposal(changed)
    assert get_proposal(proposal_record.id) == proposal_record


def test_parent_request_must_exist(proposal_record):
    missing = Proposal.model_validate(proposal_record.model_dump() | {'request_id':'request-missing'})
    with pytest.raises(sqlite3.IntegrityError):
        create_proposal(missing)
    assert get_proposal(missing.id) is None


@pytest.mark.parametrize('status',['approved','declined','scheduled'])
def test_new_proposal_must_be_pending(proposal_record,status):
    changed = Proposal.model_validate(proposal_record.model_dump() | {'status':status})
    with pytest.raises(ValueError,match='must be pending'):
        create_proposal(changed)
    assert list_proposals_for_request(proposal_record.request_id) == []


def test_multiple_proposals_allowed_and_list_is_scoped(proposal_record):
    create_proposal(proposal_record)
    another = Proposal.model_validate(proposal_record.model_dump() | {'id':'proposal-aaa'})
    create_proposal(another)
    request = get_hangout_request(proposal_record.request_id)
    second_request = HangoutRequest.model_validate(request.model_dump() | {'id':'request-other'})
    create_hangout_request(second_request)
    unrelated = Proposal.model_validate(proposal_record.model_dump() | {'id':'proposal-other','request_id':second_request.id})
    create_proposal(unrelated)
    assert list_proposals_for_request(request.id) == [another,proposal_record]
    assert list_proposals_for_request(second_request.id) == [unrelated]


def test_reads_revalidate_json(proposal_record):
    create_proposal(proposal_record)
    with connect() as connection:
        connection.execute('UPDATE proposals SET data = ? WHERE id = ?',('{}',proposal_record.id))
    with pytest.raises(ValidationError):
        get_proposal(proposal_record.id)
    with pytest.raises(ValidationError):
        list_proposals_for_request(proposal_record.request_id)
