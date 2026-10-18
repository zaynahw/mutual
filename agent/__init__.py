"""Local personal-agent lane: offline LLM client + advisory negotiation."""

from agent.local_llm import LocalLLM, LocalLLMError, LocalLLMUnavailable
from agent.negotiate import decide_plan, rank_candidate_slots
from agent.orchestrate import negotiate_hangout
from agent.schemas import (
    AgentDecision,
    NegotiationResult,
    NegotiationTurn,
    OwnerPrivateContext,
)

__all__ = [
    "LocalLLM",
    "LocalLLMError",
    "LocalLLMUnavailable",
    "rank_candidate_slots",
    "decide_plan",
    "negotiate_hangout",
    "OwnerPrivateContext",
    "AgentDecision",
    "NegotiationTurn",
    "NegotiationResult",
]
