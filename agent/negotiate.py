"""Advisory candidate ranking + personal-agent plan decisions via local LLM."""

from __future__ import annotations

import json
import re
from typing import Any, Literal, Sequence

from backend.models import CandidateOption, CandidateSlot, HangoutRequest

from agent.config import prefer_local_fallback
from agent.local_llm import ChatMessage, LocalLLM, LocalLLMError, LocalLLMUnavailable
from agent.plan_utils import (
    build_decision_from_choice,
    deterministic_fallback_plan,
    option_payload,
    private_payload,
    request_payload,
)
from agent.prompts import (
    DECIDE_SYSTEM_PROMPT,
    RANK_SYSTEM_PROMPT,
    build_decide_user_prompt,
    build_rank_user_prompt,
)
from agent.schemas import AgentDecision, MODEL_DECISION, OwnerPrivateContext


_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)

DecideMode = Literal["propose", "review"]


def rank_candidate_slots(
    request: HangoutRequest,
    candidates: Sequence[CandidateSlot],
    *,
    llm: LocalLLM | None = None,
    fallback_on_error: bool | None = None,
) -> list[CandidateSlot]:
    """Reorder (or subset) candidate slots using the local model.

    Never invents slots outside ``candidates``. On model/parse failure, either
    returns the input order (default) or raises, controlled by
    ``fallback_on_error`` / ``AGENT_LOCAL_FALLBACK``.
    """
    slots = list(candidates)
    if len(slots) <= 1:
        return slots

    client = llm or LocalLLM()
    use_fallback = prefer_local_fallback() if fallback_on_error is None else fallback_on_error

    payload = {
        "request": request_payload(request),
        "candidates": [
            {
                "index": index,
                "start": slot.start.isoformat(),
                "end": slot.end.isoformat(),
                "duration_minutes": slot.duration_minutes,
            }
            for index, slot in enumerate(slots)
        ],
    }

    try:
        raw = client.chat(
            [
                ChatMessage(role="system", content=RANK_SYSTEM_PROMPT),
                ChatMessage(role="user", content=build_rank_user_prompt(payload)),
            ],
            temperature=0.1,
            num_predict=192,
            format={
                "type": "object",
                "properties": {"ranked_indices": {"type": "array", "items": {"type": "integer", "minimum": 0, "maximum": len(slots) - 1}, "minItems": 1},
                               "reason": {"type": "string", "maxLength": 200}},
                "required": ["ranked_indices"], "additionalProperties": False,
            },
        )
        ranked = _parse_ranked_indices(raw, n=len(slots))
        return [slots[i] for i in ranked]
    except (LocalLLMUnavailable, LocalLLMError, ValueError):
        if use_fallback:
            return slots
        raise


def decide_plan(
    request: HangoutRequest,
    options: Sequence[CandidateOption],
    ctx: OwnerPrivateContext,
    *,
    mode: DecideMode = "propose",
    pending: AgentDecision | None = None,
    llm: LocalLLM | None = None,
    fallback_on_error: bool | None = None,
) -> AgentDecision:
    """Produce one personal-agent decision from CandidateOptions + private prefs.

    Private ``soft_preference_note`` is only included for ``ctx.owner_id`` and
    must never be forwarded to the other participant's agent by the caller.
    """
    opts = list(options)
    use_fallback = prefer_local_fallback() if fallback_on_error is None else fallback_on_error

    if not opts:
        return AgentDecision(decision="no_match", reason="No candidate options")

    if mode == "review" and pending is not None and pending.exact_plan() is not None:
        # Fast-path: if pending plan is still valid for this owner, model may accept.
        pass

    client = llm or LocalLLM()
    payload: dict[str, Any] = {
        "mode": mode,
        "owner": private_payload(ctx),
        "request": request_payload(request),
        "candidate_options": [option_payload(i, o) for i, o in enumerate(opts)],
    }
    if mode == "review" and pending is not None:
        payload["pending_offer"] = {
            "decision": pending.decision,
            "activity": pending.activity,
            "option_index": pending.option_index,
            "start": pending.slot.start.isoformat() if pending.slot else None,
            "end": pending.slot.end.isoformat() if pending.slot else None,
        }

    try:
        raw = client.chat(
            [
                ChatMessage(role="system", content=DECIDE_SYSTEM_PROMPT),
                ChatMessage(role="user", content=build_decide_user_prompt(payload)),
            ],
            temperature=0,
            num_predict=350,
            format=MODEL_DECISION.json_schema(),
        )
        return _parse_agent_decision(raw, request=request, options=opts, ctx=ctx, mode=mode)
    except (LocalLLMUnavailable, LocalLLMError, ValueError):
        if not use_fallback:
            raise
        if mode == "review" and pending is not None and pending.exact_plan() is not None:
            # Conservative fallback: accept a still-valid pending offer.
            try:
                return build_decision_from_choice(
                    decision="accept",
                    option_index=pending.option_index or 0,
                    activity=pending.activity,  # type: ignore[arg-type]
                    duration_minutes=int(pending.slot.duration_minutes),  # type: ignore[union-attr]
                    options=opts,
                    request=request,
                    ctx=ctx,
                    reason="Fallback accept of pending offer",
                ).model_copy(update={"used_fallback": True})
            except (ValueError, TypeError):
                pass
        return deterministic_fallback_plan(request, opts, ctx).model_copy(update={"used_fallback": True})


def _extract_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = _JSON_OBJECT_RE.search(text)
        if not match:
            raise ValueError("Model response did not contain JSON")
        data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError("Model JSON must be an object")
    return data


def _parse_ranked_indices(raw: str, *, n: int) -> list[int]:
    data = _extract_json_object(raw)
    indices = data.get("ranked_indices")
    if not isinstance(indices, list) or not indices:
        raise ValueError("ranked_indices missing or empty")

    cleaned: list[int] = []
    seen: set[int] = set()
    for item in indices:
        if not isinstance(item, int) or isinstance(item, bool):
            raise ValueError("ranked_indices must be integers")
        if item < 0 or item >= n:
            raise ValueError(f"ranked index out of range: {item}")
        if item in seen:
            continue
        seen.add(item)
        cleaned.append(item)

    for index in range(n):
        if index not in seen:
            cleaned.append(index)
    return cleaned


def _parse_agent_decision(
    raw: str,
    *,
    request: HangoutRequest,
    options: Sequence[CandidateOption],
    ctx: OwnerPrivateContext,
    mode: DecideMode,
) -> AgentDecision:
    data = MODEL_DECISION.validate_python(_extract_json_object(raw)).model_dump()
    decision = data.get("decision")
    if decision not in {"propose", "counter", "accept", "no_match"}:
        raise ValueError("invalid decision")

    if decision == "no_match":
        return AgentDecision(decision="no_match", reason=str(data.get("reason", ""))[:200])

    if mode == "propose" and decision == "accept":
        # Opening turn should propose/counter, not accept.
        decision = "propose"
    if mode == "review" and decision == "propose":
        decision = "counter"

    option_index = data.get("option_index")
    activity = data.get("activity")
    duration = data.get("duration_minutes")
    reason = str(data.get("reason", ""))[:200]

    if not isinstance(option_index, int) or isinstance(option_index, bool):
        raise ValueError("option_index must be an integer")
    if not isinstance(activity, str):
        raise ValueError("activity required")
    if not isinstance(duration, int) or isinstance(duration, bool):
        raise ValueError("duration_minutes must be an integer")

    return build_decision_from_choice(
        decision=decision,
        option_index=option_index,
        activity=activity,  # type: ignore[arg-type]
        duration_minutes=duration,
        options=options,
        request=request,
        ctx=ctx,
        reason=reason,
    )
