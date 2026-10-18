"""Approval transitions, isolation, replay, and concurrent writes."""
from concurrent.futures import ThreadPoolExecutor

import pytest

from backend.hangouts import create_hangout_request
from backend.models import Proposal
from backend.proposals import create_proposal, get_proposal_response, record_decision


@pytest.fixture
def saved(request_record):
    create_hangout_request(request_record)
    proposal = Proposal(id='proposal-test', request_id=request_record.id, activity='coffee', slot={
        'start': '2026-10-18T15:00:00-04:00', 'end': '2026-10-18T15:30:00-04:00',
    })
    create_proposal(proposal)
    return proposal, request_record


def test_two_approvals_and_replay(saved):
    proposal, request = saved
    first = record_decision(proposal.id, request.requester_id, 'approve')
    assert first.proposal.status == 'pending'
    assert len(first.approvals) == 1
    assert record_decision(proposal.id, request.requester_id, 'approve') == first
    final = record_decision(proposal.id, request.invitee_id, 'approve')
    assert final.proposal.status == 'approved'
    assert len(final.approvals) == 2
    assert get_proposal_response(proposal.id) == final
    assert record_decision(proposal.id, request.requester_id, 'approve') == final


@pytest.mark.parametrize('decision', ['approve', 'decline'])
def test_decline_closes_and_prevents_new_decisions(saved, decision):
    proposal, request = saved
    declined = record_decision(proposal.id, request.requester_id, 'decline')
    assert declined.proposal.status == 'declined'
    assert record_decision(proposal.id, request.requester_id, 'decline') == declined
    with pytest.raises(ValueError):
        record_decision(proposal.id, request.invitee_id, decision)
    assert get_proposal_response(proposal.id) == declined


def test_approve_then_other_declines_and_no_changes(saved):
    proposal, request = saved
    record_decision(proposal.id, request.requester_id, 'approve')
    with pytest.raises(ValueError):
        record_decision(proposal.id, request.requester_id, 'decline')
    assert record_decision(proposal.id, request.invitee_id, 'decline').proposal.status == 'declined'


def test_unauthorized_and_missing_do_not_write(saved):
    proposal, _ = saved
    for pid, uid in [(proposal.id, 'demo-kusum'), ('missing', 'demo-zaynah')]:
        with pytest.raises(LookupError):
            record_decision(pid, uid, 'approve')
    assert get_proposal_response(proposal.id).approvals == []


def test_concurrent_participants_and_duplicate_retries(saved):
    proposal, request = saved
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda uid: record_decision(proposal.id, uid, 'approve'),
                                [request.requester_id, request.invitee_id] * 2))
    final = get_proposal_response(proposal.id)
    assert final.proposal.status == 'approved'
    assert len(final.approvals) == 2
    assert all(len(result.approvals) in (1, 2) for result in results)


def test_api_identity_access_validation_and_reads(client, saved):
    proposal, request = saved
    path = f'/proposals/{proposal.id}/approvals'
    assert client.post(path, json={'decision': 'approve'}).status_code == 401
    assert client.post(path, headers={'X-Demo-User-Id': 'demo-kusum'}, json={'decision': 'approve'}).status_code == 404
    headers = {'X-Demo-User-Id': request.requester_id}
    assert client.post(path, headers=headers, json={'decision': 'approve', 'user_id': request.invitee_id}).status_code == 422
    assert client.post(path, headers=headers, json={'decision': 'maybe'}).status_code == 422
    response = client.post(path, headers=headers, json={'decision': 'approve'})
    assert response.status_code == 200
    assert response.json()['approvals'][0]['user_id'] == request.requester_id
    assert client.get(f'/proposals/{proposal.id}', headers=headers).json() == response.json()
    assert client.post(path, headers=headers, json={'decision': 'approve'}).json() == response.json()
    assert client.post(path, headers=headers, json={'decision': 'decline'}).status_code == 409


def test_agreed_plan_blocks_competing_decisions_and_new_proposals(saved):
    proposal, request = saved
    competing = proposal.model_copy(update={'id': 'proposal-competing'})
    create_proposal(competing)
    record_decision(competing.id, request.requester_id, 'approve')
    record_decision(proposal.id, request.requester_id, 'approve')
    record_decision(proposal.id, request.invitee_id, 'approve')
    for user_id, decision in [(request.requester_id, 'approve'), (request.invitee_id, 'approve'), (request.invitee_id, 'decline')]:
        with pytest.raises(ValueError, match='already has an agreed plan'):
            record_decision(competing.id, user_id, decision)
    with pytest.raises(ValueError, match='already has an agreed plan'):
        create_proposal(proposal.model_copy(update={'id': 'proposal-new'}))
    assert get_proposal_response(competing.id).proposal.status == 'pending'
    assert len(get_proposal_response(competing.id).approvals) == 1
    assert record_decision(proposal.id, request.requester_id, 'approve').proposal.status == 'approved'


def test_declined_history_does_not_block_replacement_and_requests_are_independent(saved):
    proposal, request = saved
    record_decision(proposal.id, request.requester_id, 'decline')
    replacement = proposal.model_copy(update={'id': 'replacement'})
    create_proposal(replacement)
    for uid in (request.requester_id, request.invitee_id):
        record_decision(replacement.id, uid, 'approve')
    other_request = request.model_copy(update={'id': 'other-request'})
    create_hangout_request(other_request)
    unrelated = proposal.model_copy(update={'id': 'unrelated', 'request_id': other_request.id})
    create_proposal(unrelated)
    assert record_decision(unrelated.id, request.requester_id, 'approve').proposal.status == 'pending'


def test_concurrent_final_approvals_choose_only_one_option(saved):
    proposal, request = saved
    competing = proposal.model_copy(update={'id': 'competing'})
    create_proposal(competing)
    for pid in (proposal.id, competing.id):
        record_decision(pid, request.requester_id, 'approve')
    def finish(pid):
        try:
            return record_decision(pid, request.invitee_id, 'approve').proposal.status
        except ValueError:
            return 'conflict'
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(finish, [proposal.id, competing.id]))
    assert sorted(results) == ['approved', 'conflict']
    assert sorted(get_proposal_response(pid).proposal.status for pid in (proposal.id, competing.id)) == ['approved', 'pending']


def test_competing_option_api_returns_conflict(client, saved):
    proposal, request = saved
    competing = proposal.model_copy(update={'id': 'competing'})
    create_proposal(competing)
    for uid in (request.requester_id, request.invitee_id):
        record_decision(proposal.id, uid, 'approve')
    response = client.post(f'/proposals/{competing.id}/approvals',
                           headers={'X-Demo-User-Id': request.invitee_id}, json={'decision': 'approve'})
    assert response.status_code == 409
    assert response.json() == {'detail': 'This hangout already has an agreed plan'}
