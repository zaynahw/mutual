"""Local personal-agent lane: offline LLM client + advisory negotiation."""

from agent.local_llm import LocalLLM, LocalLLMError, LocalLLMUnavailable
from agent.negotiate import rank_candidate_slots

__all__ = [
    "LocalLLM",
    "LocalLLMError",
    "LocalLLMUnavailable",
    "rank_candidate_slots",
]
