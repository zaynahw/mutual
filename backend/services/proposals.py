"""Validate exact recommendations against fresh candidates before persistence.

Caller authorization belongs to routes. No agent calls, approvals, or calendar
writes occur here. Future manual, agent, and fallback inputs share this service.
"""
from datetime import timezone
from uuid import uuid4

from backend.models import CandidateOption, HangoutRequest, Proposal, ProposalCreate
from backend.proposals import create_proposal
from backend.creation_receipts import get_receipt
from backend.services.calendar_adapter import CalendarAdapter
from backend.services.candidates import build_candidates


def fits_candidate(recommendation: ProposalCreate, candidate: CandidateOption) -> bool:
    return (
        recommendation.activity in candidate.eligible_activities
        and recommendation.slot.duration_minutes in candidate.eligible_durations
        and recommendation.slot.start.astimezone(timezone.utc) >= candidate.slot.start.astimezone(timezone.utc)
        and recommendation.slot.end.astimezone(timezone.utc) <= candidate.slot.end.astimezone(timezone.utc)
    )


async def create_validated_proposal(
    request: HangoutRequest,
    recommendation: ProposalCreate,
    calendar: CalendarAdapter,
    approved_by: str | None = None,
    idempotency_key: str | None = None,
) -> Proposal:
    if approved_by is not None:
        replay = get_receipt(approved_by, idempotency_key, f'proposal:{request.id}', recommendation.model_dump(mode='json'))
        if replay is not None:
            return Proposal.model_validate_json(replay)
    candidates = await build_candidates(request, calendar)
    if not any(fits_candidate(recommendation, candidate) for candidate in candidates):
        raise ValueError("The proposed plan no longer fits valid availability")

    proposal = Proposal(
        **recommendation.model_dump(),
        id=f"proposal-{uuid4()}",
        request_id=request.id,
        location=request.location,
        status="pending",
    )
    return create_proposal(proposal, approved_by, idempotency_key)
