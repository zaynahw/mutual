"""Adapter only. The agent lane owns the local model and negotiation."""

from __future__ import annotations

import asyncio
from typing import Protocol

from backend.models import CandidateSlot, HangoutRequest


class AgentAdapter(Protocol):
    async def evaluate(
        self, request: HangoutRequest, candidates: list[CandidateSlot]
    ) -> list[CandidateSlot]: ...


class MockAgentAdapter:
    async def evaluate(
        self, request: HangoutRequest, candidates: list[CandidateSlot]
    ) -> list[CandidateSlot]:
        # Deterministic passthrough for integration demos; no model behavior.
        return list(candidates)


class LocalAgentAdapter:
    """Ranks candidate slots with the offline Ollama model in agent/."""

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


def build_agent_adapter(name: str | None = None) -> AgentAdapter:
    """Factory used by backend wiring. Defaults to AGENT_ADAPTER env var."""
    import os

    selected = (name or os.environ.get("AGENT_ADAPTER", "mock")).strip().lower()
    if selected in {"local", "ollama", "local_llm"}:
        return LocalAgentAdapter()
    return MockAgentAdapter()
