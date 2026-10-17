"""Advisory candidate ranking via the local offline LLM."""

from __future__ import annotations

import json
import re
from typing import Sequence

from backend.models import CandidateSlot, HangoutRequest

from agent.config import prefer_local_fallback
from agent.local_llm import ChatMessage, LocalLLM, LocalLLMError, LocalLLMUnavailable
from agent.prompts import RANK_SYSTEM_PROMPT, build_rank_user_prompt


_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


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
        "request": {
            "id": request.id,
            "requester_id": request.requester_id,
            "invitee_id": request.invitee_id,
            "start": request.start.isoformat(),
            "end": request.end.isoformat(),
            "allowed_activities": list(request.allowed_activities),
            "allowed_durations": list(request.allowed_durations),
            "location": request.location,
        },
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
        )
        ranked = _parse_ranked_indices(raw, n=len(slots))
        return [slots[i] for i in ranked]
    except (LocalLLMUnavailable, LocalLLMError, ValueError):
        if use_fallback:
            return slots
        raise


def _parse_ranked_indices(raw: str, *, n: int) -> list[int]:
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

    # Append any omitted indices so we never drop slots unless the model
    # explicitly returned a proper subset (already handled by seen).
    for index in range(n):
        if index not in seen:
            cleaned.append(index)
    return cleaned
