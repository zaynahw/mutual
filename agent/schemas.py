"""Agreed agent↔backend negotiation contract (advisory; backend revalidates)."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, TypeAdapter

from backend.models import (
    Activity,
    CandidateSlot,
    DemoUserId,
    DurationMinutes,
    Model,
    ProposalCreate,
)


class OwnerPrivateContext(Model):
    """Isolated owner context. Never forward one owner's note to the other agent."""

    owner_id: DemoUserId
    preferred_activities: list[Activity] = Field(default_factory=list)
    soft_preference_note: str = Field(default="", max_length=1000)
    max_duration_minutes: DurationMinutes = 120
    timezone: str = "America/New_York"


class AgentDecision(Model):
    """Single personal-agent turn. propose/counter carry an exact plan; accept does too."""

    decision: Literal["propose", "counter", "accept", "no_match"]
    activity: Activity | None = None
    slot: CandidateSlot | None = None
    option_index: int | None = Field(default=None, ge=0)
    reason: str = Field(default="", max_length=200)
    used_fallback: bool = False

    def exact_plan(self) -> ProposalCreate | None:
        if self.decision == "no_match" or self.activity is None or self.slot is None:
            return None
        return ProposalCreate(activity=self.activity, slot=self.slot)


class ModelPlanChoice(Model):
    """Wire format requested from Ollama, before resolving an exact slot."""

    decision: Literal["propose", "counter", "accept"]
    option_index: Annotated[int, Field(strict=True, ge=0)]
    activity: Activity
    duration_minutes: DurationMinutes
    reason: str = Field(default="", max_length=200)


class ModelNoMatch(Model):
    decision: Literal["no_match"]
    reason: str = Field(default="", max_length=200)


MODEL_DECISION = TypeAdapter(ModelPlanChoice | ModelNoMatch)


class NegotiationTurn(Model):
    actor_id: DemoUserId
    decision: AgentDecision


class NegotiationResult(Model):
    """Outcome of bounded two-agent negotiation. Backend maps agreed → Proposal."""

    status: Literal["agreed", "no_match", "exhausted"]
    proposal: ProposalCreate | None = None
    turns: list[NegotiationTurn] = Field(default_factory=list)
    reason: str = Field(default="", max_length=500)
