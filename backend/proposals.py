"""Internal proposal storage; services validate and authorize plans.

Initialize the database first. These functions do not validate a plan against
availability, establish caller identity, or approve/create calendar events.
"""
from datetime import datetime, timezone
from typing import Literal

from backend.database import connect
from backend.models import Approval, Proposal, ProposalResponse
from backend.creation_receipts import read_receipt, save_receipt


def _agreed_proposal(connection, request_id: str) -> Proposal | None:
    rows = connection.execute(
        'SELECT data FROM proposals WHERE request_id = ? ORDER BY id', (request_id,),
    ).fetchall()
    for row in rows:
        proposal = Proposal.model_validate_json(row['data'])
        if proposal.status in ('approved', 'scheduled'):
            return proposal
    return None


def create_proposal(
    proposal: Proposal, approved_by: str | None = None, idempotency_key: str | None = None,
) -> Proposal:
    """Insert only; initial state must be pending. Integrity errors propagate."""
    if proposal.status != "pending":
        raise ValueError("New proposals must be pending")
    with connect() as connection:
        connection.execute('BEGIN IMMEDIATE')
        payload = {'activity': proposal.activity, 'slot': proposal.slot.model_dump(mode='json')}
        operation = f'proposal:{proposal.request_id}'
        if approved_by is not None:
            replay = read_receipt(connection, approved_by, idempotency_key, operation, payload)
            if replay is not None:
                return Proposal.model_validate_json(replay)
            request = connection.execute('SELECT requester_id, invitee_id FROM hangout_requests WHERE id = ?', (proposal.request_id,)).fetchone()
            if request is None or approved_by not in (request['requester_id'], request['invitee_id']):
                raise LookupError('Proposal not found')
        if _agreed_proposal(connection, proposal.request_id) is not None:
            raise ValueError('This hangout already has an agreed plan')
        connection.execute(
            "INSERT INTO proposals (id, request_id, data) VALUES (?, ?, ?)",
            (proposal.id, proposal.request_id, proposal.model_dump_json()),
        )
        if approved_by is not None:
            connection.execute(
                "INSERT INTO approvals (proposal_id, user_id, decision, decided_at) VALUES (?, ?, 'approve', ?)",
                (proposal.id, approved_by, datetime.now(timezone.utc).isoformat()),
            )
            save_receipt(connection, approved_by, idempotency_key, operation, payload, proposal.model_dump_json())
    return proposal


def get_proposal(proposal_id: str) -> Proposal | None:
    with connect() as connection:
        row = connection.execute(
            "SELECT data FROM proposals WHERE id = ?", (proposal_id,),
        ).fetchone()
    if row is None:
        return None
    return Proposal.model_validate_json(row["data"])


def list_proposals_for_request(request_id: str) -> list[Proposal]:
    with connect() as connection:
        rows = connection.execute(
            "SELECT data FROM proposals WHERE request_id = ? ORDER BY id", (request_id,),
        ).fetchall()
    return [Proposal.model_validate_json(row["data"]) for row in rows]


def _read_response(connection, proposal_id: str) -> ProposalResponse:
    row = connection.execute('SELECT data FROM proposals WHERE id = ?', (proposal_id,)).fetchone()
    if row is None:
        raise LookupError('Proposal not found')
    approvals = connection.execute(
        'SELECT proposal_id, user_id, decision, decided_at FROM approvals WHERE proposal_id = ? ORDER BY user_id',
        (proposal_id,),
    ).fetchall()
    return ProposalResponse(
        proposal=Proposal.model_validate_json(row['data']),
        approvals=[Approval.model_validate(dict(item)) for item in approvals],
    )


def get_proposal_response(proposal_id: str) -> ProposalResponse:
    with connect() as connection:
        # Keep proposal state and its decisions in the same read snapshot.
        connection.execute('BEGIN')
        return _read_response(connection, proposal_id)


def record_decision(proposal_id: str, user_id: str, decision: Literal['approve', 'decline']) -> ProposalResponse:
    if decision not in ('approve', 'decline'):
        raise ValueError('Invalid decision')
    with connect() as connection:
        connection.execute('BEGIN IMMEDIATE')
        result = _read_response(connection, proposal_id)
        request = connection.execute(
            'SELECT requester_id, invitee_id FROM hangout_requests WHERE id = ?',
            (result.proposal.request_id,),
        ).fetchone()
        if request is None or user_id not in (request['requester_id'], request['invitee_id']):
            raise LookupError('Proposal not found')
        agreed = _agreed_proposal(connection, result.proposal.request_id)
        if agreed is not None and agreed.id != proposal_id:
            raise ValueError('This hangout already has an agreed plan')
        previous = next((item for item in result.approvals if item.user_id == user_id), None)
        if previous is not None:
            if previous.decision == decision:
                return result
            raise ValueError('A recorded decision cannot be changed')
        if result.proposal.status != 'pending':
            raise ValueError('This proposal is closed to new decisions')
        approval = Approval(
            proposal_id=proposal_id, user_id=user_id,
            decision=decision, decided_at=datetime.now(timezone.utc),
        )
        connection.execute(
            'INSERT INTO approvals (proposal_id, user_id, decision, decided_at) VALUES (?, ?, ?, ?)',
            (proposal_id, user_id, decision, approval.decided_at.isoformat()),
        )
        approvals = [*result.approvals, approval]
        status = 'declined' if any(item.decision == 'decline' for item in approvals) else 'approved' if len(approvals) == 2 else 'pending'
        proposal = Proposal.model_validate(result.proposal.model_dump() | {'status': status})
        connection.execute('UPDATE proposals SET data = ? WHERE id = ?', (proposal.model_dump_json(), proposal_id))
        return _read_response(connection, proposal_id)


def replan_proposal(proposal_id: str, user_id: str) -> ProposalResponse:
    """Cancel an unscheduled suggestion and its alternatives; preserve all decisions."""
    with connect() as connection:
        connection.execute('BEGIN IMMEDIATE')
        result = _read_response(connection, proposal_id)
        request = connection.execute('SELECT requester_id, invitee_id FROM hangout_requests WHERE id = ?', (result.proposal.request_id,)).fetchone()
        if request is None or user_id not in (request['requester_id'], request['invitee_id']):
            raise LookupError('Proposal not found')
        agreed = _agreed_proposal(connection, result.proposal.request_id)
        if result.proposal.status == 'cancelled':
            return result
        if agreed is not None and agreed.id != proposal_id:
            raise ValueError('Replan the agreed option instead')
        rows = connection.execute('SELECT data FROM proposals WHERE request_id = ?', (result.proposal.request_id,)).fetchall()
        proposals = [Proposal.model_validate_json(row['data']) for row in rows]
        for proposal in proposals:
            event = connection.execute('SELECT status, external_started FROM calendar_events WHERE proposal_id = ?', (proposal.id,)).fetchone()
            if proposal.status == 'scheduled' or event is not None and (event['status'] in ('creating', 'completed') or event['external_started']):
                raise ValueError('Calendar creation may have started; resolve the calendar result before replanning')
        for proposal in proposals:
            if proposal.status in ('pending', 'approved'):
                cancelled = Proposal.model_validate(proposal.model_dump() | {'status': 'cancelled'})
                connection.execute('UPDATE proposals SET data = ? WHERE id = ?', (cancelled.model_dump_json(), proposal.id))
        return _read_response(connection, proposal_id)
