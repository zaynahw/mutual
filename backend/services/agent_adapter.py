"""Adapter only. The agent lane owns the local model and negotiation."""

from __future__ import annotations

import asyncio
import os
from typing import Literal, Protocol

from backend.models import CandidateOption, CandidateSlot, HangoutRequest, User

from agent.schemas import NegotiationResult, OwnerPrivateContext


class AgentAdapter(Protocol):
    source: Literal["local_agent", "mock"]

    async def evaluate(
        self, request: HangoutRequest, candidates: list[CandidateSlot]
    ) -> list[CandidateSlot]: ...

    async def negotiate(
        self,
        request: HangoutRequest,
        options: list[CandidateOption],
        requester_ctx: OwnerPrivateContext,
        invitee_ctx: OwnerPrivateContext,
        *,
        max_rounds: int = 3,
    ) -> NegotiationResult: ...


class MockAgentAdapter:
    """Deterministic demos: passthrough rank + first eligible exact plan."""

    source: Literal["mock"] = "mock"

    async def evaluate(
        self, request: HangoutRequest, candidates: list[CandidateSlot]
    ) -> list[CandidateSlot]:
        return list(candidates)

    async def negotiate(
        self,
        request: HangoutRequest,
        options: list[CandidateOption],
        requester_ctx: OwnerPrivateContext,
        invitee_ctx: OwnerPrivateContext,
        *,
        max_rounds: int = 3,
    ) -> NegotiationResult:
        from agent.plan_utils import deterministic_fallback_plan
        from agent.schemas import NegotiationResult, NegotiationTurn

        if not options:
            return NegotiationResult(status="no_match", reason="No candidate options")

        decision = deterministic_fallback_plan(request, options, requester_ctx)
        plan = decision.exact_plan()
        if plan is None:
            return NegotiationResult(
                status="no_match",
                reason=decision.reason or "No eligible plan",
                turns=[
                    NegotiationTurn(actor_id=requester_ctx.owner_id, decision=decision),
                ],
            )
        # Mock invitee always accepts the deterministic plan.
        from agent.schemas import AgentDecision

        accept = AgentDecision(
            decision="accept",
            activity=decision.activity,
            slot=decision.slot,
            option_index=decision.option_index,
            reason="Mock invitee accepts",
        )
        return NegotiationResult(
            status="agreed",
            proposal=plan,
            reason="Mock two-party agreement",
            turns=[
                NegotiationTurn(actor_id=requester_ctx.owner_id, decision=decision),
                NegotiationTurn(actor_id=invitee_ctx.owner_id, decision=accept),
            ],
        )


class LocalAgentAdapter:
    """Offline Ollama ranking + bounded two-agent negotiation."""

    source: Literal["local_agent"] = "local_agent"

    def __init__(self, *, fallback_on_error: bool | None = None) -> None:
        self.fallback_on_error = fallback_on_error

    async def evaluate(
        self, request: HangoutRequest, candidates: list[CandidateSlot]
    ) -> list[CandidateSlot]:
        from agent.negotiate import rank_candidate_slots

        return await asyncio.to_thread(
            rank_candidate_slots,
            request,
            candidates,
            fallback_on_error=self.fallback_on_error,
        )

    async def negotiate(
        self,
        request: HangoutRequest,
        options: list[CandidateOption],
        requester_ctx: OwnerPrivateContext,
        invitee_ctx: OwnerPrivateContext,
        *,
        max_rounds: int = 3,
    ) -> NegotiationResult:
        from agent.orchestrate import negotiate_hangout

        return await asyncio.to_thread(
            negotiate_hangout,
            request,
            options,
            requester_ctx,
            invitee_ctx,
            max_rounds=max_rounds,
            fallback_on_error=self.fallback_on_error,
        )


def build_agent_adapter(name: str | None = None) -> AgentAdapter:
    """Factory used by backend wiring. Defaults to AGENT_ADAPTER env var."""
    selected = (name or os.environ.get("AGENT_ADAPTER", "mock")).strip().lower()
    if selected in {"local", "ollama", "local_llm"}:
        return LocalAgentAdapter()
    if selected == "mock":
        return MockAgentAdapter()
    raise ValueError("Unknown AGENT_ADAPTER; choose mock or local")


def owner_context_from_user(user: User) -> OwnerPrivateContext:
    """Helper for backend routes: map private User → agent context."""
    return OwnerPrivateContext(
        owner_id=user.id,
        preferred_activities=list(user.preferences.preferred_activities),
        soft_preference_note=user.preferences.soft_preference_note,
        max_duration_minutes=user.hard_constraints.max_duration_minutes,
        timezone=user.timezone,
    )
