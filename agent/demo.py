#!/usr/bin/env python3
"""Live demo: local Ollama ranks/negotiates hangout CandidateOptions.

Usage (repo root, Ollama serving llama3.2:1b):
    python -m agent.demo
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone

from backend.models import CandidateOption, CandidateSlot, HangoutRequest

from agent.local_llm import LocalLLM, LocalLLMUnavailable
from agent.orchestrate import negotiate_hangout
from agent.schemas import OwnerPrivateContext


def dt(date: str, time: str) -> datetime:
    return datetime.fromisoformat(f"{date}T{time}+00:00")


def main() -> None:
    llm = LocalLLM()
    print("=== Mutual Agent Negotiate Demo ===")
    print(f"Ollama: {llm.base_url}  model={llm.model}")

    try:
        models = llm.list_models()
    except LocalLLMUnavailable as exc:
        print(f"UNAVAILABLE: {exc}")
        print("Start Ollama, then re-run. Example: ~/local_llm/scripts/phase1_chat.sh")
        sys.exit(1)
    print(f"Models: {', '.join(models) or '(none)'}")

    request = HangoutRequest(
        id="req-demo-001",
        requester_id="demo-zaynah",
        invitee_id="demo-daniella",
        start=dt("2026-10-18", "09:00:00"),
        end=dt("2026-10-18", "20:00:00"),
        allowed_activities=["coffee", "walk"],
        allowed_durations=[30, 60],
        location="Tech Square",
    )
    options = [
        CandidateOption(
            slot=CandidateSlot(
                start=dt("2026-10-18", "15:00:00"),
                end=dt("2026-10-18", "16:00:00"),
            ),
            eligible_activities=["coffee"],
            eligible_durations=[30, 60],
        ),
        CandidateOption(
            slot=CandidateSlot(
                start=dt("2026-10-18", "11:00:00"),
                end=dt("2026-10-18", "12:00:00"),
            ),
            eligible_activities=["coffee", "walk"],
            eligible_durations=[30, 60],
        ),
    ]
    requester = OwnerPrivateContext(
        owner_id="demo-zaynah",
        preferred_activities=["coffee"],
        soft_preference_note="Prefer late morning if possible",
    )
    invitee = OwnerPrivateContext(
        owner_id="demo-daniella",
        preferred_activities=["walk", "coffee"],
        soft_preference_note="Happy with either; shorter is fine",
    )

    print("\nRunning two-agent negotiate_hangout …")
    result = negotiate_hangout(
        request, options, requester, invitee, llm=llm, max_rounds=3
    )
    print(f"Status:  {result.status}")
    print(f"Reason:  {result.reason}")
    if result.proposal:
        p = result.proposal
        print(
            f"Plan:    {p.activity} "
            f"{p.slot.start.astimezone(timezone.utc).isoformat()} → "
            f"{p.slot.end.astimezone(timezone.utc).isoformat()}"
        )
    print(f"Turns:   {len(result.turns)}")
    for turn in result.turns:
        d = turn.decision
        print(f"  - {turn.actor_id}: {d.decision} {d.activity} {d.reason}")


if __name__ == "__main__":
    main()
