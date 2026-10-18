"""Adapter only. The agent lane owns the local model and negotiation."""

from __future__ import annotations

import asyncio
import os
from typing import Literal, Protocol
from datetime import date

from backend.models import CandidateOption, CandidateSlot, HangoutRequest, User, HangoutIntentCreate, IntentInterpretationResult

from agent.schemas import NegotiationResult, OwnerPrivateContext


class AgentAdapter(Protocol):
    source: Literal["local_agent", "mock"]

    async def interpret(self, body: HangoutIntentCreate, timezone: str, today: date) -> IntentInterpretationResult: ...

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

    async def interpret(self, body: HangoutIntentCreate, timezone: str, today: date) -> IntentInterpretationResult:
        from agent.interpret import deterministic_interpret
        return IntentInterpretationResult(source='mock', interpretation=deterministic_interpret(body,today))


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

    async def interpret(self, body: HangoutIntentCreate, timezone: str, today: date) -> IntentInterpretationResult:
        from agent.interpret import interpret_message
        return await asyncio.to_thread(interpret_message,body,timezone,today,fallback_on_error=self.fallback_on_error)

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
        from agent.negotiate import LocalLLM
        from copy import deepcopy

        permitted = compact_options(options)

        class ConstrainedClient(LocalLLM):
            def chat(self, messages, **kwargs):
                import json
                from agent.local_llm import ChatMessage, LocalLLMError
                # A flat union gives Ollama complete valid response shapes.
                # Nested partial branches can make the no_match shape the only
                # readily generated response in a small constrained model.
                schema = deepcopy(kwargs.get("format"))
                definition = schema.get("$defs", {}).get("ModelPlanChoice") if isinstance(schema, dict) else None
                if definition:
                    variants = []
                    for index, option in enumerate(permitted):
                        variant = deepcopy(definition)
                        properties = variant["properties"]
                        properties["option_index"] = {"type":"integer", "const":index}
                        properties["activity"]["enum"] = list(option.eligible_activities)
                        properties["duration_minutes"]["enum"] = list(option.eligible_durations)
                        variants.append(variant)
                    variants.append(deepcopy(schema["$defs"]["ModelNoMatch"]))
                    kwargs["format"] = {"anyOf":variants}
                for attempt in range(2):
                    raw = super().chat(messages, **kwargs)
                    try:
                        value = json.loads(raw)
                        if value.get("decision") == "no_match":
                            return raw
                        index = value.get("option_index")
                        if type(index) is not int or not 0 <= index < len(permitted):
                            raise ValueError()
                        option = permitted[index]
                        if value.get("activity") not in option.eligible_activities or value.get("duration_minutes") not in option.eligible_durations:
                            raise ValueError()
                        return raw
                    except (ValueError, TypeError, AttributeError):
                        if attempt:
                            raise LocalLLMError("Local model did not select an eligible option") from None
                        # No raw output or private reasoning is echoed or logged.
                        messages = list(messages) + [ChatMessage(role="user", content=
                            "Your response did not select a valid combination. Select an option_index from candidate_options, "
                            "then choose activity and duration_minutes from THAT option's eligible lists. Return only the decision JSON.")]

        return await asyncio.to_thread(
            negotiate_hangout,
            request,
            permitted,
            requester_ctx,
            invitee_ctx,
            max_rounds=max_rounds,
            llm=ConstrainedClient(),
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


def compact_options(options: list[CandidateOption]) -> list[CandidateOption]:
    """Group identical time/duration choices so activity selection is unambiguous.

    This changes only the internal representation, never the permitted plan set.
    Backend validation still uses the original authorized candidates.
    """
    grouped: dict[tuple, CandidateOption] = {}
    for option in options:
        key = (option.slot.start, option.slot.end, tuple(sorted(option.eligible_durations)))
        if key not in grouped:
            grouped[key] = option.model_copy(deep=True)
        else:
            current = grouped[key]
            current.eligible_activities = list(dict.fromkeys(
                current.eligible_activities + option.eligible_activities))
    return list(grouped.values())
