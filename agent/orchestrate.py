"""Bounded two-agent negotiation. Backend calls this; still advisory only."""

from __future__ import annotations

from typing import Sequence

from backend.models import CandidateOption, HangoutRequest

from agent.config import prefer_local_fallback
from agent.local_llm import LocalLLM
from agent.negotiate import decide_plan
from agent.plan_utils import same_plan
from agent.schemas import (
    AgentDecision,
    NegotiationResult,
    NegotiationTurn,
    OwnerPrivateContext,
)


DEFAULT_MAX_ROUNDS = 3


def negotiate_hangout(
    request: HangoutRequest,
    options: Sequence[CandidateOption],
    requester_ctx: OwnerPrivateContext,
    invitee_ctx: OwnerPrivateContext,
    *,
    max_rounds: int = DEFAULT_MAX_ROUNDS,
    llm: LocalLLM | None = None,
    fallback_on_error: bool | None = None,
) -> NegotiationResult:
    """Run requester → invitee → … turns until agree, no_match, or rounds exhausted.

    Privacy: each ``decide_plan`` call receives only that owner's private context.
    Shared inputs are the hangout request and candidate options only.
    """
    if requester_ctx.owner_id != request.requester_id:
        raise ValueError("requester_ctx.owner_id must match request.requester_id")
    if invitee_ctx.owner_id != request.invitee_id:
        raise ValueError("invitee_ctx.owner_id must match request.invitee_id")
    if max_rounds < 1:
        raise ValueError("max_rounds must be >= 1")

    opts = list(options)
    use_fallback = prefer_local_fallback() if fallback_on_error is None else fallback_on_error
    turns: list[NegotiationTurn] = []

    if not opts:
        return NegotiationResult(
            status="no_match",
            reason="No candidate options to negotiate",
            turns=turns,
        )

    opening = decide_plan(
        request,
        opts,
        requester_ctx,
        mode="propose",
        llm=llm,
        fallback_on_error=use_fallback,
    )
    turns.append(NegotiationTurn(actor_id=requester_ctx.owner_id, decision=opening))
    if opening.decision == "no_match" or opening.exact_plan() is None:
        return NegotiationResult(
            status="no_match",
            turns=turns,
            reason=opening.reason or "Requester agent found no plan",
        )

    pending: AgentDecision = opening

    for round_idx in range(max_rounds):
        reviewer_ctx = invitee_ctx if round_idx % 2 == 0 else requester_ctx
        reviewer = decide_plan(
            request,
            opts,
            reviewer_ctx,
            mode="review",
            pending=pending,
            llm=llm,
            fallback_on_error=use_fallback,
        )
        turns.append(NegotiationTurn(actor_id=reviewer_ctx.owner_id, decision=reviewer))

        if reviewer.decision == "accept":
            agreed = pending.exact_plan()
            # If reviewer echoed a concrete plan, require it matches pending.
            if reviewer.exact_plan() is not None and not same_plan(
                reviewer.exact_plan(), pending.exact_plan()
            ):
                # Treat mismatched "accept" as a counter instead of agreeing.
                pending = reviewer
                continue
            return NegotiationResult(
                status="agreed",
                proposal=agreed,
                turns=turns,
                reason=reviewer.reason or "Both agents aligned",
            )

        if reviewer.decision == "no_match":
            return NegotiationResult(
                status="no_match",
                turns=turns,
                reason=reviewer.reason or "Agent declared no_match",
            )

        if reviewer.exact_plan() is not None:
            pending = reviewer
            continue

        return NegotiationResult(
            status="no_match",
            turns=turns,
            reason="Reviewer returned an unusable decision",
        )

    return NegotiationResult(
        status="exhausted",
        turns=turns,
        reason=f"No agreement within {max_rounds} review rounds",
    )
