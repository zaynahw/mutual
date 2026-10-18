"""Revalidate approved plans, then finalize through an idempotent calendar adapter."""
from hashlib import sha256

from backend.calendar_events import claim_event, complete_event, release_event, mark_event_writing
from backend.models import CalendarEventResponse
from backend.services.calendar_adapter import CalendarAdapter
from backend.services.candidates import build_candidates
from backend.services.proposals import fits_candidate
from backend.services.schedule import CalendarUnavailable


async def finalize_proposal(
    proposal_id: str, user_id: str, key: str, calendar: CalendarAdapter,
) -> tuple[CalendarEventResponse, bool]:
    attempt = claim_event(proposal_id, user_id, key)
    if attempt.event_id is not None:
        return CalendarEventResponse(proposal_id=proposal_id, event_id=attempt.event_id), False
    try:
        provider_key = 'mutual-' + sha256(proposal_id.encode()).hexdigest()
        participants = [attempt.request.requester_id, attempt.request.invitee_id]
        finder = getattr(calendar, 'find_event', None)
        if finder is not None:
            try:
                recovered = await finder(attempt.proposal, participants, provider_key)
            except Exception as error:
                raise CalendarUnavailable() from error
            if recovered:
                complete_event(attempt, recovered)
                return CalendarEventResponse(proposal_id=proposal_id,event_id=recovered), False
        candidates = await build_candidates(attempt.request, calendar)
        if not any(fits_candidate(attempt.proposal, candidate) for candidate in candidates):
            raise ValueError('This plan no longer fits current availability')
        # Stable across client keys, workers, restarts, and ambiguous provider errors.
        provider_key = 'mutual-' + sha256(proposal_id.encode()).hexdigest()
        mark_event_writing(attempt)
        try:
            event_id = await calendar.create_event(
                attempt.proposal,
                [attempt.request.requester_id, attempt.request.invitee_id],
                provider_key,
            )
            if not isinstance(event_id, str) or not event_id.strip():
                raise RuntimeError('Calendar returned an invalid event ID')
        except Exception as error:
            raise CalendarUnavailable() from error
        complete_event(attempt, event_id)
        return CalendarEventResponse(proposal_id=proposal_id, event_id=event_id), True
    finally:
        # Completed claims are unaffected; failures/cancellation can be retried.
        release_event(attempt)
