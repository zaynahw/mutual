"""Bridge backend-authorized candidates to isolated agents and safe public results."""
import asyncio
from datetime import timedelta
from uuid import uuid4
from typing import Literal

from agent.config import max_negotiate_rounds
from agent.schemas import NegotiationResult
from backend.creation_receipts import get_receipt
from backend.models import CandidateOption, HangoutRequest, NegotiationResponse, Proposal, PublicNegotiationTurn
from backend.negotiations import save_negotiation
from backend.proposals import list_proposals_for_request
from backend.repositories import get_user
from backend.intents import request_intent
from backend.services.agent_adapter import AgentAdapter, owner_context_from_user
from backend.services.calendar_adapter import CalendarAdapter
from backend.services.candidates import build_candidates
from backend.services.proposals import fits_candidate

NEGOTIATION_TIMEOUT_SECONDS = 120


class AgentUnavailable(Exception):
    """Inference failed or produced an unusable result. Never expose raw errors."""


async def negotiate_request(
    request: HangoutRequest, actor_id: str, key: str, calendar: CalendarAdapter, agent: AgentAdapter,
    variation: Literal["any", "different_time"] = "any",
) -> NegotiationResponse:
    if actor_id not in (request.requester_id, request.invitee_id):
        raise LookupError('Hangout request not found')
    payload = {} if variation == 'any' else {'variation':variation}
    replay = get_receipt(actor_id, key, f'negotiate:{request.id}', payload)
    if replay is not None:
        return NegotiationResponse.model_validate_json(replay)
    previous = list_proposals_for_request(request.id)
    if any(plan.status in ('approved', 'scheduled') for plan in previous):
        raise ValueError('This hangout already has an agreed plan')
    options = await build_candidates(request, calendar)
    had_options = bool(options)
    if previous:
        options = unseen_options(options, previous, different_time=variation == "different_time")
    # Profiles are loaded after calendar waits, not accepted from the client.
    requester, invitee = get_user(request.requester_id), get_user(request.invitee_id)
    if requester is None or invitee is None:
        raise LookupError('Participant not found')
    intent = request_intent(request.id,requester.id)
    try:
        if options:
            requester_ctx = owner_context_from_user(requester)
            if intent is not None:
                requester_ctx = requester_ctx.model_copy(update={
                    'request_preferences':intent.input.message,
                    'preferred_periods':intent.result.interpretation.preferred_periods,
                })
            raw = await asyncio.wait_for(agent.negotiate(
                request, options, requester_ctx, owner_context_from_user(invitee),
                max_rounds=min(3, max_negotiate_rounds()),
            ), timeout=NEGOTIATION_TIMEOUT_SECONDS)
            result = NegotiationResult.model_validate(raw)
        else:
            result = NegotiationResult(status='no_match')
        source = 'mock' if agent.source == 'mock' else 'demo_fallback' if any(turn.decision.used_fallback for turn in result.turns) else 'local_agent'
        if intent is not None and intent.result.source == 'demo_fallback':
            source = 'demo_fallback'
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
        from agent.local_llm import LocalLLMUnavailable, LocalLLMError
        if isinstance(error, LocalLLMUnavailable):
            message = "The local AI service is unreachable. Check that Ollama is running, then retry."
        elif isinstance(error, (asyncio.TimeoutError, TimeoutError)):
            message = "The agents took too long to respond. Your existing suggestions are saved; retry this search."
        elif isinstance(error, (LocalLLMError, ValueError)):
            message = "The local AI could not return a valid plan. No new suggestion was saved. Please retry."
        else:
            message = "Agent negotiation is temporarily unavailable. Your existing suggestions are saved; please retry."
        raise AgentUnavailable(message) from error
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
        candidate_count=len(options),
        outcome_code=("no_new_options" if had_options and previous and not options else "no_eligible_options" if not options else "agents_no_match") if result.status == "no_match" else "round_limit" if result.status == "exhausted" else None,
    ), payload=payload)


def unseen_options(options: list[CandidateOption], previous: list[Proposal], *, different_time: bool = False) -> list[CandidateOption]:
    """Offer new exact choices, including later starts inside a free interval.

    Each record is an exact duration so containment validation cannot accidentally
    admit an excluded earlier plan. Keep the model's choice set bounded.
    """
    offered = {(p.activity, p.slot.start, p.slot.end) for p in previous}
    previous_starts = {p.slot.start for p in previous}
    choices = {}
    for option in options:
        start = option.slot.start
        while start < option.slot.end:
            if different_time and start in previous_starts:
                start += timedelta(minutes=30)
                continue
            for duration in option.eligible_durations:
                end = start + timedelta(minutes=duration)
                if end > option.slot.end:
                    continue
                for activity in option.eligible_activities:
                    key = (activity, start, end)
                    if key not in offered:
                        choices[key] = CandidateOption(
                            slot={'start':start, 'end':end},
                            eligible_activities=[activity], eligible_durations=[duration],
                        )
            start += timedelta(minutes=30)
    return sorted(choices.values(), key=lambda o: (o.slot.start, o.slot.end, o.eligible_activities[0]))[:48]
