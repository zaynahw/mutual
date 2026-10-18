"""Atomically save sanitized negotiation results and retry receipts, never approvals."""
from backend.creation_receipts import read_receipt, save_receipt
from backend.database import connect
from backend.models import NegotiationResponse
from backend.proposals import _agreed_proposal


def save_negotiation(
    request_id: str, actor_id: str, key: str, result: NegotiationResponse,
) -> NegotiationResponse:
    with connect() as connection:
        connection.execute('BEGIN IMMEDIATE')
        request = connection.execute('SELECT requester_id, invitee_id FROM hangout_requests WHERE id = ?', (request_id,)).fetchone()
        if request is None or actor_id not in (request['requester_id'], request['invitee_id']):
            raise LookupError('Hangout request not found')
        replay = read_receipt(connection, actor_id, key, f'negotiate:{request_id}', {})
        if replay is not None:
            return NegotiationResponse.model_validate_json(replay)
        if _agreed_proposal(connection, request_id) is not None:
            raise ValueError('This hangout already has an agreed plan')
        if result.proposal is not None:
            proposal = result.proposal
            if result.status != 'agreed' or proposal.request_id != request_id or proposal.status != 'pending':
                raise ValueError('Invalid negotiation result')
            connection.execute('INSERT INTO proposals (id, request_id, data) VALUES (?, ?, ?)',
                               (proposal.id, request_id, proposal.model_dump_json()))
        save_receipt(connection, actor_id, key, f'negotiate:{request_id}', {}, result.model_dump_json())
        return result
