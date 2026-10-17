"""Adapter only. The agent lane owns the local model and negotiation."""
from typing import Protocol
from backend.models import CandidateSlot, HangoutRequest

class AgentAdapter(Protocol):
    async def evaluate(self, request: HangoutRequest, candidates: list[CandidateSlot]) -> list[CandidateSlot]: ...

class MockAgentAdapter:
    async def evaluate(self, request: HangoutRequest, candidates: list[CandidateSlot]) -> list[CandidateSlot]:
        # Deterministic passthrough for integration demos; no model behavior.
        return list(candidates)

class LocalAgentAdapter:
    async def evaluate(self, request: HangoutRequest, candidates: list[CandidateSlot]) -> list[CandidateSlot]:
        raise NotImplementedError("Agent teammate supplies local model integration")
