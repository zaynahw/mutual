"""Durable event claims. No database transaction spans a calendar network call."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from backend.database import connect
from backend.models import HangoutRequest, Proposal

# A crashed worker can be retried after this lease; provider idempotency is required.
CLAIM_LEASE = timedelta(minutes=5)


@dataclass(frozen=True)
class EventAttempt:
    proposal: Proposal
    request: HangoutRequest
    token: str
    event_id: str | None = None


def claim_event(proposal_id: str, user_id: str, key: str) -> EventAttempt:
    with connect() as connection:
        connection.execute('BEGIN IMMEDIATE')
        row = connection.execute('SELECT data FROM proposals WHERE id = ?', (proposal_id,)).fetchone()
        if row is None:
            raise LookupError('Proposal not found')
        proposal = Proposal.model_validate_json(row['data'])
        row = connection.execute('SELECT data FROM hangout_requests WHERE id = ?', (proposal.request_id,)).fetchone()
        if row is None:
            raise LookupError('Proposal not found')
        request = HangoutRequest.model_validate_json(row['data'])
        participants = {request.requester_id, request.invitee_id}
        if user_id not in participants:
            raise LookupError('Proposal not found')
        approvals = connection.execute(
            'SELECT user_id, decision FROM approvals WHERE proposal_id = ?', (proposal_id,),
        ).fetchall()
        if proposal.status not in ('approved', 'scheduled') or {row['user_id'] for row in approvals if row['decision'] == 'approve'} != participants:
            raise ValueError('Both participants must approve before scheduling')
        existing_key = connection.execute(
            'SELECT proposal_id FROM calendar_event_keys WHERE idempotency_key = ?', (key,),
        ).fetchone()
        if existing_key is not None and existing_key['proposal_id'] != proposal_id:
            raise ValueError('This idempotency key belongs to another proposal')
        connection.execute(
            'INSERT OR IGNORE INTO calendar_event_keys (idempotency_key, proposal_id) VALUES (?, ?)',
            (key, proposal_id),
        )
        event = connection.execute('SELECT * FROM calendar_events WHERE proposal_id = ?', (proposal_id,)).fetchone()
        if event is not None and event['status'] == 'completed':
            return EventAttempt(proposal, request, event['claim_token'], event['event_id'])
        if proposal.status == 'scheduled':
            raise ValueError('Scheduled proposal has no saved calendar result')
        now = datetime.now(timezone.utc)
        if event is not None and event['status'] == 'creating' and now - datetime.fromisoformat(event['updated_at']) < CLAIM_LEASE:
            raise ValueError('Calendar creation is already in progress; retry shortly')
        token = str(uuid4())
        connection.execute('''
            INSERT INTO calendar_events (proposal_id, status, claim_token, updated_at)
            VALUES (?, 'creating', ?, ?)
            ON CONFLICT(proposal_id) DO UPDATE SET status = 'creating',
                claim_token = excluded.claim_token, updated_at = excluded.updated_at
        ''', (proposal_id, token, now.isoformat()))
        return EventAttempt(proposal, request, token)


def release_event(attempt: EventAttempt) -> None:
    with connect() as connection:
        connection.execute('''UPDATE calendar_events SET status = 'retryable', updated_at = ?
            WHERE proposal_id = ? AND claim_token = ? AND status = 'creating'
        ''', (datetime.now(timezone.utc).isoformat(), attempt.proposal.id, attempt.token))


def complete_event(attempt: EventAttempt, event_id: str) -> None:
    with connect() as connection:
        connection.execute('BEGIN IMMEDIATE')
        updated = connection.execute('''UPDATE calendar_events
            SET status = 'completed', event_id = ?, updated_at = ?
            WHERE proposal_id = ? AND claim_token = ? AND status = 'creating'
        ''', (event_id, datetime.now(timezone.utc).isoformat(), attempt.proposal.id, attempt.token))
        if updated.rowcount != 1:
            raise ValueError('Calendar attempt changed; retry to retrieve the result')
        scheduled = Proposal.model_validate(attempt.proposal.model_dump() | {'status': 'scheduled'})
        connection.execute('UPDATE proposals SET data = ? WHERE id = ?', (scheduled.model_dump_json(), scheduled.id))


def mark_event_writing(attempt: EventAttempt) -> None:
    with connect() as connection:
        updated = connection.execute(
            "UPDATE calendar_events SET external_started = 1 WHERE proposal_id = ? AND claim_token = ? AND status = 'creating'",
            (attempt.proposal.id, attempt.token),
        )
        if updated.rowcount != 1:
            raise ValueError('Calendar attempt changed; refresh before retrying')
