"""Bridge backend-authorized candidates to isolated agents and safe public results."""
import asyncio
from uuid import uuid4

from agent.config import max_negotiate_rounds
from agent.schemas import NegotiationResult
from backend.creation_receipts import get_receipt
from backend.models import HangoutRequest, NegotiationResponse, Proposal, PublicNegotiationTurn
from backend.negotiations import save_negotiation
from backend.proposals import list_proposals_for_request
from backend.repositories import get_user
from backend.services.agent_adapter import AgentAdapter, owner_context_from_user
from backend.services.calendar_adapter import CalendarAdapter
from backend.services.candidates import build_candidates
from backend.services.proposals import fits_candidate

NEGOTIATION_TIMEOUT_SECONDS = 120


class AgentUnavailable(Exception):
    """Inference failed or produced an unusable result. Never expose raw errors."""


async def negotiate_request(
    request: HangoutRequest, actor_id: str, key: str, calendar: CalendarAdapter, agent: AgentAdapter,
) -> NegotiationResponse:
    if actor_id not in (request.requester_id, request.invitee_id):
        raise LookupError('Hangout request not found')
    replay = get_receipt(actor_id, key, f'negotiate:{request.id}', {})
    if replay is not None:
        return NegotiationResponse.model_validate_json(replay)
    if any(plan.status in ('approved', 'scheduled') for plan in list_proposals_for_request(request.id)):
        raise ValueError('This hangout already has an agreed plan')
    options = await build_candidates(request, calendar)
    # Profiles are loaded after calendar waits, not accepted from the client.
    requester, invitee = get_user(request.requester_id), get_user(request.invitee_id)
    if requester is None or invitee is None:
        raise LookupError('Participant not found')
    try:
        if options:
            raw = await asyncio.wait_for(agent.negotiate(
                request, options, owner_context_from_user(requester), owner_context_from_user(invitee),
                max_rounds=min(3, max_negotiate_rounds()),
            ), timeout=NEGOTIATION_TIMEOUT_SECONDS)
            result = NegotiationResult.model_validate(raw)
        else:
            result = NegotiationResult(status='no_match')
        source = 'mock' if agent.source == 'mock' else 'demo_fallback' if any(turn.decision.used_fallback for turn in result.turns) else 'local_agent'
        public_turns = []
        for turn in result.turns:
            if turn.actor_id not in (request.requester_id, request.invitee_id):
                raise ValueError('Invalid agent identity')
            decision = turn.decision
            # Return only choices that fit the authorized candidates; never reasons.
            if decision.decision != 'no_match':
                exact = decision.exact_plan()
                if exact is None or not any(fits_candidate(exact, option) for option in options):
                    raise ValueError('Invalid agent turn')
            public_turns.append(PublicNegotiationTurn(
                actor_id=turn.actor_id, decision=decision.decision,
                activity=decision.activity if decision.decision != 'no_match' else None,
                slot=decision.slot if decision.decision != 'no_match' else None,
            ))
        if result.status == 'agreed' and result.proposal is None:
            raise ValueError('Missing recommendation')
    except Exception as error:
        raise AgentUnavailable() from error
    if result.status == 'agreed' and not any(fits_candidate(result.proposal, option) for option in options):
        raise ValueError('Agent recommendation does not fit the provided options')
    proposal = None
    if result.status == 'agreed':
        # Fresh permissions, hard constraints, and free/busy after model inference.
        fresh = await build_candidates(request, calendar)
        if not any(fits_candidate(result.proposal, option) for option in fresh):
            raise ValueError('The suggested plan no longer fits current availability')
        proposal = Proposal(
            **result.proposal.model_dump(), id=f'proposal-{uuid4()}', request_id=request.id,
            location=request.location, status='pending', source=source,
        )
    return save_negotiation(request.id, actor_id, key, NegotiationResponse(
        status=result.status, source=source, proposal=proposal, turns=public_turns,
    ))
