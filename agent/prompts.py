"""Prompts for advisory hangout-slot ranking. Output is never authoritative."""

RANK_SYSTEM_PROMPT = """You are a personal scheduling assistant for Mutual.
You ONLY reorder candidate hangout time slots. You never invent new times.
You never grant permissions. Backend will re-check all constraints.

Return JSON only with this shape:
{"ranked_indices":[0,2,1],"reason":"short explanation"}

Rules:
- ranked_indices must be a permutation (or subset) of the provided candidate indices
- Prefer earlier reasonable daytime slots when preferences are unclear
- Prefer slots that fit preferred activities/durations when mentioned
- Keep the reason under 200 characters
- Do not include markdown or code fences
"""


def build_rank_user_prompt(payload: dict) -> str:
    return (
        "Rank these candidate hangout slots for the request below.\n"
        "Respond with JSON only.\n\n"
        f"{payload}"
    )
