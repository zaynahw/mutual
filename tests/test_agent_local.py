"""Unit tests for the local Ollama agent lane (no live model required)."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from urllib.error import URLError

import pytest

from agent.local_llm import LocalLLM, LocalLLMUnavailable
from agent.negotiate import _parse_ranked_indices, rank_candidate_slots
from backend.models import CandidateSlot, HangoutRequest
from backend.services.agent_adapter import LocalAgentAdapter, MockAgentAdapter, build_agent_adapter


def _request() -> HangoutRequest:
    return HangoutRequest(
        id="req-1",
        requester_id="demo-zaynah",
        invitee_id="demo-daniella",
        start=datetime(2026, 10, 18, 10, 0, tzinfo=timezone.utc),
        end=datetime(2026, 10, 18, 18, 0, tzinfo=timezone.utc),
        allowed_activities=["coffee", "walk"],
        allowed_durations=[30, 60],
    )


def _slots() -> list[CandidateSlot]:
    return [
        CandidateSlot(
            start=datetime(2026, 10, 18, 16, 0, tzinfo=timezone.utc),
            end=datetime(2026, 10, 18, 17, 0, tzinfo=timezone.utc),
        ),
        CandidateSlot(
            start=datetime(2026, 10, 18, 11, 0, tzinfo=timezone.utc),
            end=datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc),
        ),
        CandidateSlot(
            start=datetime(2026, 10, 18, 13, 0, tzinfo=timezone.utc),
            end=datetime(2026, 10, 18, 14, 0, tzinfo=timezone.utc),
        ),
    ]


def test_parse_ranked_indices_permutation_and_fill():
    assert _parse_ranked_indices('{"ranked_indices":[2,0],"reason":"x"}', n=3) == [2, 0, 1]


def test_parse_ranked_indices_rejects_out_of_range():
    with pytest.raises(ValueError):
        _parse_ranked_indices('{"ranked_indices":[9]}', n=2)


def test_rank_uses_model_order(monkeypatch):
    class FakeLLM:
        def chat(self, messages, **kwargs):
            return '{"ranked_indices":[1,2,0],"reason":"earlier first"}'

    ranked = rank_candidate_slots(_request(), _slots(), llm=FakeLLM(), fallback_on_error=False)
    assert [s.start.hour for s in ranked] == [11, 13, 16]


def test_rank_falls_back_when_unavailable():
    class DeadLLM:
        def chat(self, messages, **kwargs):
            raise LocalLLMUnavailable("down")

    original = _slots()
    ranked = rank_candidate_slots(
        _request(), original, llm=DeadLLM(), fallback_on_error=True
    )
    assert ranked == original


def test_local_llm_unavailable(monkeypatch):
    def boom(*args, **kwargs):
        raise URLError("refused")

    monkeypatch.setattr("urllib.request.urlopen", boom)
    with pytest.raises(LocalLLMUnavailable):
        LocalLLM(base_url="http://127.0.0.1:9").list_models()


def test_local_llm_chat_ok(monkeypatch):
    body = json.dumps({"message": {"content": "hello from local"}}).encode()

    class Resp:
        def read(self):
            return body

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: Resp())
    assert LocalLLM().chat([{"role": "user", "content": "hi"}]) == "hello from local"


def test_local_agent_adapter_async(monkeypatch):
    class FakeLLM:
        def chat(self, messages, **kwargs):
            return '{"ranked_indices":[1,0,2],"reason":"ok"}'

    monkeypatch.setattr("agent.negotiate.LocalLLM", lambda: FakeLLM())
    adapter = LocalAgentAdapter(fallback_on_error=False)
    ranked = asyncio.run(adapter.evaluate(_request(), _slots()))
    assert [s.start.hour for s in ranked] == [11, 16, 13]


def test_build_agent_adapter(monkeypatch):
    monkeypatch.setenv("AGENT_ADAPTER", "mock")
    assert isinstance(build_agent_adapter(), MockAgentAdapter)
    assert isinstance(build_agent_adapter("local"), LocalAgentAdapter)
