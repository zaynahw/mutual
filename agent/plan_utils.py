"""Deterministic helpers to validate / build exact plans from CandidateOptions."""

from __future__ import annotations

from datetime import timedelta
from typing import Sequence

from backend.models import (
    Activity,
    CandidateOption,
    CandidateSlot,
    DurationMinutes,
    HangoutRequest,
    ProposalCreate,
)

from agent.schemas import AgentDecision, OwnerPrivateContext


SUPPORTED_DURATIONS = (30, 60, 90, 120)


def option_payload(index: int, option: CandidateOption) -> dict:
    return {
        "index": index,
        "start": option.slot.start.isoformat(),
        "end": option.slot.end.isoformat(),
        "duration_minutes": option.slot.duration_minutes,
        "eligible_activities": list(option.eligible_activities),
        "eligible_durations": list(option.eligible_durations),
    }


def request_payload(request: HangoutRequest) -> dict:
    return {
        "id": request.id,
        "requester_id": request.requester_id,
        "invitee_id": request.invitee_id,
        "start": request.start.isoformat(),
        "end": request.end.isoformat(),
        "allowed_activities": list(request.allowed_activities),
        "allowed_durations": list(request.allowed_durations),
        "location": request.location,
    }


def private_payload(ctx: OwnerPrivateContext) -> dict:
    return {
        "owner_id": ctx.owner_id,
        "preferred_activities": list(ctx.preferred_activities),
        "soft_preference_note": ctx.soft_preference_note,
        "max_duration_minutes": ctx.max_duration_minutes,
        "timezone": ctx.timezone,
    }


def exact_slot_from_option(option: CandidateOption, duration_minutes: int) -> CandidateSlot:
    if duration_minutes not in SUPPORTED_DURATIONS:
        raise ValueError("Unsupported duration")
    if duration_minutes > option.slot.duration_minutes:
        raise ValueError("Duration does not fit option slot")
    end = option.slot.start + timedelta(minutes=duration_minutes)
    return CandidateSlot(start=option.slot.start, end=end)


def allowed_activity(
    option: CandidateOption,
    request: HangoutRequest,
    activity: Activity,
) -> bool:
    return activity in option.eligible_activities and activity in request.allowed_activities


def allowed_duration(
    option: CandidateOption,
    request: HangoutRequest,
    ctx: OwnerPrivateContext,
    duration: int,
) -> bool:
    return (
        duration in option.eligible_durations
        and duration in request.allowed_durations
        and duration <= ctx.max_duration_minutes
        and duration <= option.slot.duration_minutes
        and duration in SUPPORTED_DURATIONS
    )


def build_decision_from_choice(
    *,
    decision: str,
    option_index: int,
    activity: Activity,
    duration_minutes: int,
    options: Sequence[CandidateOption],
    request: HangoutRequest,
    ctx: OwnerPrivateContext,
    reason: str = "",
) -> AgentDecision:
    if option_index < 0 or option_index >= len(options):
        raise ValueError("option_index out of range")
    option = options[option_index]
    if not allowed_activity(option, request, activity):
        raise ValueError("activity not eligible")
    if not allowed_duration(option, request, ctx, duration_minutes):
        raise ValueError("duration not eligible")
    slot = exact_slot_from_option(option, duration_minutes)
    return AgentDecision(
        decision=decision,  # type: ignore[arg-type]
        activity=activity,
        slot=slot,
        option_index=option_index,
        reason=reason[:200],
    )


def deterministic_fallback_plan(
    request: HangoutRequest,
    options: Sequence[CandidateOption],
    ctx: OwnerPrivateContext,
) -> AgentDecision:
    """Pick a valid plan without the LLM (prefer preferred activities, then earliest)."""
    if not options:
        return AgentDecision(decision="no_match", reason="No candidate options")

    preferred = set(ctx.preferred_activities)

    def score(index: int, option: CandidateOption) -> tuple:
        acts = [
            a
            for a in option.eligible_activities
            if a in request.allowed_activities
        ]
        durs = [
            d
            for d in option.eligible_durations
            if allowed_duration(option, request, ctx, d)
        ]
        pref_hit = 0 if any(a in preferred for a in acts) else 1
        return (pref_hit, option.slot.start.timestamp(), index, acts, durs)

    ranked = sorted((score(i, o) for i, o in enumerate(options)), key=lambda t: t[:3])
    for pref_hit, _ts, index, acts, durs in ranked:
        if not acts or not durs:
            continue
        activity = next((a for a in acts if a in preferred), acts[0])
        duration = min(durs)
        return build_decision_from_choice(
            decision="propose",
            option_index=index,
            activity=activity,
            duration_minutes=duration,
            options=options,
            request=request,
            ctx=ctx,
            reason="Deterministic fallback plan",
        )

    return AgentDecision(decision="no_match", reason="No eligible activity/duration overlap")


def same_plan(a: ProposalCreate | None, b: ProposalCreate | None) -> bool:
    if a is None or b is None:
        return False
    return (
        a.activity == b.activity
        and a.slot.start == b.slot.start
        and a.slot.end == b.slot.end
    )
