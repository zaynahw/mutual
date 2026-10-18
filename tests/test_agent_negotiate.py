"""Tests for agent decide_plan + two-agent orchestration (no live Ollama)."""

from __future__ import annotations

import asyncio
from datetime import datetime

import pytest

from agent.local_llm import LocalLLMUnavailable
from agent.negotiate import decide_plan, rank_candidate_slots, _parse_ranked_indices
from agent.orchestrate import negotiate_hangout
from agent.plan_utils import deterministic_fallback_plan
from agent.schemas import OwnerPrivateContext
from backend.models import CandidateOption, CandidateSlot, HangoutRequest
from backend.services.agent_adapter import (
    LocalAgentAdapter,
    MockAgentAdapter,
    build_agent_adapter,
    owner_context_from_user,
)
from backend.models import HardConstraints, Preferences, User


def dt(time: str) -> datetime:
    return datetime.fromisoformat(f"2026-10-18T{time}+00:00")


def slot(start: str, end: str) -> CandidateSlot:
    return CandidateSlot(start=dt(start), end=dt(end))


def make_request(**overrides) -> HangoutRequest:
    base = dict(
        id="req-test-001",
        requester_id="demo-zaynah",
        invitee_id="demo-daniella",
        start=dt("09:00:00"),
        end=dt("20:00:00"),
        allowed_activities=["coffee", "walk"],
        allowed_durations=[30, 60],
        location="Tech Square",
    )
    base.update(overrides)
    return HangoutRequest(**base)


def make_options() -> list[CandidateOption]:
    return [
        CandidateOption(
            slot=slot("15:00:00", "16:00:00"),
            eligible_activities=["coffee"],
            eligible_durations=[30, 60],
        ),
        CandidateOption(
            slot=slot("11:00:00", "12:00:00"),
            eligible_activities=["coffee", "walk"],
            eligible_durations=[30, 60],
        ),
    ]


def ctx(owner_id: str, preferred=None, note: str = "") -> OwnerPrivateContext:
    return OwnerPrivateContext(
        owner_id=owner_id,
        preferred_activities=preferred or [],
        soft_preference_note=note,
        max_duration_minutes=120,
    )


class StubLLM:
    def __init__(self, *responses: str) -> None:
        self._responses = list(responses)
        self.calls = 0

    def chat(self, messages, **kwargs) -> str:
        self.calls += 1
        if not self._responses:
            raise AssertionError("StubLLM has no more responses")
        return self._responses.pop(0)


class FailingLLM:
    def chat(self, messages, **kwargs) -> str:
        raise LocalLLMUnavailable("down")


# ---------- ranking (legacy) ----------

def test_parse_ranked_indices_basic():
    assert _parse_ranked_indices('{"ranked_indices": [2, 0, 1]}', n=3) == [2, 0, 1]


def test_rank_reorders():
    candidates = [slot("09:00:00", "10:00:00"), slot("14:00:00", "15:00:00")]
    out = rank_candidate_slots(
        make_request(),
        candidates,
        llm=StubLLM('{"ranked_indices":[1,0]}'),
        fallback_on_error=False,
    )
    assert out == [candidates[1], candidates[0]]


# ---------- decide_plan ----------

def test_decide_plan_propose_from_model():
    decision = decide_plan(
        make_request(),
        make_options(),
        ctx("demo-zaynah", preferred=["walk"]),
        mode="propose",
        llm=StubLLM(
            '{"decision":"propose","option_index":1,"activity":"walk","duration_minutes":30,"reason":"morning walk"}'
        ),
        fallback_on_error=False,
    )
    assert decision.decision == "propose"
    assert decision.activity == "walk"
    assert decision.option_index == 1
    assert decision.slot is not None
    assert decision.slot.duration_minutes == 30
    assert decision.slot.start == dt("11:00:00")


def test_decide_plan_rejects_illegal_activity():
    with pytest.raises(ValueError):
        decide_plan(
            make_request(),
            make_options(),
            ctx("demo-zaynah"),
            llm=StubLLM(
                '{"decision":"propose","option_index":0,"activity":"concert","duration_minutes":30,"reason":"x"}'
            ),
            fallback_on_error=False,
        )


def test_decide_plan_fallback_deterministic():
    decision = decide_plan(
        make_request(),
        make_options(),
        ctx("demo-zaynah", preferred=["walk"]),
        llm=FailingLLM(),
        fallback_on_error=True,
    )
    assert decision.decision == "propose"
    assert decision.activity == "walk"
    assert decision.option_index == 1  # walk only on option 1


def test_deterministic_fallback_no_match_when_empty():
    d = deterministic_fallback_plan(make_request(), [], ctx("demo-zaynah"))
    assert d.decision == "no_match"


# ---------- orchestration ----------

def test_negotiate_agrees_when_invitee_accepts():
    llm = StubLLM(
        '{"decision":"propose","option_index":1,"activity":"coffee","duration_minutes":30,"reason":"am coffee"}',
        '{"decision":"accept","option_index":1,"activity":"coffee","duration_minutes":30,"reason":"ok"}',
    )
    result = negotiate_hangout(
        make_request(),
        make_options(),
        ctx("demo-zaynah", note="I like mornings"),
        ctx("demo-daniella", note="secret invitee note"),
        llm=llm,
        fallback_on_error=False,
    )
    assert result.status == "agreed"
    assert result.proposal is not None
    assert result.proposal.activity == "coffee"
    assert result.proposal.slot.duration_minutes == 30
    assert len(result.turns) == 2
    assert llm.calls == 2


def test_negotiate_counter_then_accept():
    llm = StubLLM(
        '{"decision":"propose","option_index":0,"activity":"coffee","duration_minutes":60,"reason":"pm"}',
        '{"decision":"counter","option_index":1,"activity":"walk","duration_minutes":30,"reason":"prefer walk"}',
        '{"decision":"accept","option_index":1,"activity":"walk","duration_minutes":30,"reason":"deal"}',
    )
    result = negotiate_hangout(
        make_request(),
        make_options(),
        ctx("demo-zaynah"),
        ctx("demo-daniella"),
        max_rounds=3,
        llm=llm,
        fallback_on_error=False,
    )
    assert result.status == "agreed"
    assert result.proposal is not None
    assert result.proposal.activity == "walk"
    assert len(result.turns) == 3


def test_negotiate_no_match():
    llm = StubLLM(
        '{"decision":"propose","option_index":0,"activity":"coffee","duration_minutes":30,"reason":"x"}',
        '{"decision":"no_match","reason":"busy"}',
    )
    result = negotiate_hangout(
        make_request(),
        make_options(),
        ctx("demo-zaynah"),
        ctx("demo-daniella"),
        llm=llm,
        fallback_on_error=False,
    )
    assert result.status == "no_match"
    assert result.proposal is None


def test_negotiate_privacy_owner_ids_checked():
    with pytest.raises(ValueError, match="requester_ctx"):
        negotiate_hangout(
            make_request(),
            make_options(),
            ctx("demo-kusum"),
            ctx("demo-daniella"),
            llm=StubLLM("{}"),
        )


# ---------- adapter ----------

def test_mock_adapter_negotiate():
    adapter = MockAgentAdapter()
    result = asyncio.run(
        adapter.negotiate(
            make_request(),
            make_options(),
            ctx("demo-zaynah", preferred=["coffee"]),
            ctx("demo-daniella"),
        )
    )
    assert result.status == "agreed"
    assert result.proposal is not None


def test_local_adapter_negotiate_with_stub(monkeypatch):
    responses = [
        '{"decision":"propose","option_index":1,"activity":"coffee","duration_minutes":30,"reason":"a"}',
        '{"decision":"accept","option_index":1,"activity":"coffee","duration_minutes":30,"reason":"b"}',
    ]

    class QueueLLM:
        def chat(self, messages, **kwargs):
            return responses.pop(0)

    monkeypatch.setattr("agent.negotiate.LocalLLM", QueueLLM)
    adapter = LocalAgentAdapter(fallback_on_error=False)
    result = asyncio.run(
        adapter.negotiate(
            make_request(),
            make_options(),
            ctx("demo-zaynah"),
            ctx("demo-daniella"),
        )
    )
    assert result.status == "agreed"


def test_build_adapter_and_owner_context():
    assert isinstance(build_agent_adapter("mock"), MockAgentAdapter)
    assert isinstance(build_agent_adapter("local"), LocalAgentAdapter)
    user = User(
        id="demo-zaynah",
        display_name="Zaynah (demo)",
        preferences=Preferences(
            preferred_activities=["coffee"],
            soft_preference_note="quiet cafes",
        ),
        hard_constraints=HardConstraints(
            allowed_activities=["coffee", "walk"],
            max_duration_minutes=90,
        ),
    )
    oc = owner_context_from_user(user)
    assert oc.owner_id == "demo-zaynah"
    assert oc.soft_preference_note == "quiet cafes"
    assert oc.max_duration_minutes == 90


def test_accept_requires_an_exact_choice_and_no_match_remains_valid():
    with pytest.raises(ValueError):
        decide_plan(make_request(),make_options(),ctx('demo-daniella'),mode='review',
                    llm=StubLLM('{"decision":"accept","reason":"yes"}'),fallback_on_error=False)
    decision = decide_plan(make_request(),make_options(),ctx('demo-daniella'),mode='review',
                           llm=StubLLM('{"decision":"no_match","reason":"none acceptable"}'),fallback_on_error=False)
    assert decision.decision == 'no_match'
