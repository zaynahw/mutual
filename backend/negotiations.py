"""Atomically save sanitized negotiation results and retry receipts, never approvals."""
from backend.creation_receipts import read_receipt, save_receipt
from backend.database import connect
from backend.models import NegotiationResponse
from backend.proposals import _agreed_proposal


def save_negotiation(
    request_id: str, actor_id: str, key: str, result: NegotiationResponse, *, payload: dict | None = None,
) -> NegotiationResponse:
    payload = payload or {}
    with connect() as connection:
        connection.execute('BEGIN IMMEDIATE')
        request = connection.execute('SELECT requester_id, invitee_id FROM hangout_requests WHERE id = ?', (request_id,)).fetchone()
        if request is None or actor_id not in (request['requester_id'], request['invitee_id']):
            raise LookupError('Hangout request not found')
        replay = read_receipt(connection, actor_id, key, f'negotiate:{request_id}', payload)
        if replay is not None:
            return NegotiationResponse.model_validate_json(replay)
        if _agreed_proposal(connection, request_id) is not None:
            raise ValueError('This hangout already has an agreed plan')
        if result.proposal is not None:
            proposal = result.proposal
            if result.status != 'agreed' or proposal.request_id != request_id or proposal.status != 'pending':
                raise ValueError('Invalid negotiation result')
            existing = connection.execute('SELECT data FROM proposals WHERE request_id = ?', (request_id,)).fetchall()
            from backend.models import Proposal
            for row in existing:
                old = Proposal.model_validate_json(row['data'])
                if old.activity == proposal.activity and old.slot == proposal.slot:
                    raise ValueError('This option was already suggested; ask for another option again')
            connection.execute('INSERT INTO proposals (id, request_id, data) VALUES (?, ?, ?)',
                               (proposal.id, request_id, proposal.model_dump_json()))
        save_receipt(connection, actor_id, key, f'negotiate:{request_id}', payload, result.model_dump_json())
        return result


def latest_negotiation(request_id: str, actor_id: str) -> NegotiationResponse | None:
    """Read only sanitized receipts after checking current request participation."""
    with connect() as connection:
        request = connection.execute(
            'SELECT requester_id, invitee_id FROM hangout_requests WHERE id = ?', (request_id,),
        ).fetchone()
        if request is None or actor_id not in (request['requester_id'], request['invitee_id']):
            raise LookupError('Hangout request not found')
        row = connection.execute(
            'SELECT response FROM creation_receipts WHERE operation = ? ORDER BY rowid DESC LIMIT 1',
            (f'negotiate:{request_id}',),
        ).fetchone()
        return NegotiationResponse.model_validate_json(row['response']) if row else None
