# Agent lane — local model + negotiation

Offline personal-agent stack for Mutual. Uses a locally running Ollama model
(`llama3.2:1b` by default). Model output is **advisory only**; the backend must
revalidate permissions, intervals, boundaries, and approvals.

## What it does

1. **Rank** (legacy): reorder `CandidateSlot`s.
2. **Decide**: one owner's agent picks `propose` / `counter` / `accept` / `no_match`
   from `CandidateOption`s using that owner's private prefs only.
3. **Orchestrate**: bounded two-agent negotiation → `NegotiationResult`
   (`agreed` + exact `ProposalCreate`, or `no_match` / `exhausted`).

## Layout

| Path | Role |
|---|---|
| `schemas.py` | `OwnerPrivateContext`, `AgentDecision`, `NegotiationResult` |
| `local_llm.py` | HTTP client for local Ollama |
| `plan_utils.py` | Validate options → exact duration-sized slots; deterministic fallback |
| `negotiate.py` | `rank_candidate_slots`, `decide_plan` |
| `orchestrate.py` | `negotiate_hangout` (two agents, max rounds) |
| `prompts.py` | JSON-only ranking / decision prompts |
| `config.py` | Host, model, fallback, rounds |
| `demo.py` | Live Ollama smoke demo |

Backend: `backend/services/agent_adapter.py`
(`LocalAgentAdapter` / `MockAgentAdapter` / `build_agent_adapter` /
`owner_context_from_user`).

## Contract (I/O)

**Shared input**

- `HangoutRequest`
- `list[CandidateOption]` (backend-filtered)

**Private input (per owner, never cross-sent)**

```json
{
  "owner_id": "demo-zaynah",
  "preferred_activities": ["coffee"],
  "soft_preference_note": "quiet cafes near campus",
  "max_duration_minutes": 90,
  "timezone": "America/New_York"
}
```

**Turn JSON from the model**

```json
{
  "decision": "propose",
  "option_index": 1,
  "activity": "coffee",
  "duration_minutes": 30,
  "reason": "morning coffee"
}
```

**Orchestration output**

```json
{
  "status": "agreed",
  "proposal": {
    "activity": "coffee",
    "slot": {"start": "2026-10-18T11:00:00+00:00", "end": "2026-10-18T11:30:00+00:00"}
  },
  "turns": ["…"],
  "reason": "Both agents aligned"
}
```

When backend implements `POST /hangout-requests/{id}/negotiate`, call:

```python
adapter = build_agent_adapter()  # AGENT_ADAPTER=local|mock
result = await adapter.negotiate(
    request, options,
    owner_context_from_user(requester),
    owner_context_from_user(invitee),
)
# if result.status == "agreed": create Proposal from result.proposal + location
```

## Configure

```env
AGENT_ADAPTER=local
OLLAMA_HOST=http://127.0.0.1:11434
OLLAMA_MODEL=llama3.2:1b
AGENT_LOCAL_FALLBACK=1
AGENT_MAX_ROUNDS=3
```

## Demo

```sh
# Terminal with Ollama up (e.g. ~/local_llm/scripts/phase1_chat.sh)
.venv/bin/python -m agent.demo
```

## Privacy

Each `decide_plan` call receives **one** owner's `soft_preference_note`.
Orchestration never passes owner A's note into owner B's prompt.

## Backend integration in this branch

POST /hangout-requests/{id}/negotiate is now wired. It requires participant demo
identity and an Idempotency-Key. The backend creates candidates, loads both owner
contexts, and validates the final recommendation again after inference. It saves
pending proposals with **zero human approvals**. Manual proposals remain separate.

Shared pending offers omit free-text reasons, and public traces contain only
validated structured choices. The response and saved proposal label source as
local_agent, demo_fallback, or mock. Any fallback turn marks the whole outcome
as demo_fallback; mock results never claim inference. Backend review rounds are
capped at three, with a 120-second overall timeout returning a generic 502.

Environment variables must be exported in the server shell; root .env is not
loaded automatically. For a real inference check, run Ollama with the model
already available, then start the backend with:

```sh
AGENT_ADAPTER=local AGENT_LOCAL_FALLBACK=0 uvicorn backend.main:app --reload --port 8000
```

Choose a request with valid candidates on /demo.html and click Let agents suggest
a plan. With fallback disabled, model failures are visible errors rather than
simulated agreement. Default AGENT_ADAPTER=mock runs without Ollama.

## Structured responses

LocalLLM.chat sends Ollama a JSON schema through format. Negotiation requires
option_index, activity, and duration_minutes for propose/counter/accept; no_match
uses a separate schema. Prompt inputs are serialized as JSON, and negotiation
uses temperature 0 with a 350-token output budget. Truncated responses are rejected.
Schema constraints do not replace candidate checks, privacy checks, or human consent.
Model weights live in Ollama’s model storage, outside this repository; agent/ contains
our prompts, client, negotiation logic, and schemas.
