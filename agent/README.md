# Agent lane — local model

Offline personal-agent stack for Mutual. Uses a locally running Ollama model
(`llama3.2:1b` by default). Model output is **advisory only**; the backend must
revalidate permissions, intervals, boundaries, and approvals.

## Layout

| Path | Role |
|---|---|
| `local_llm.py` | HTTP client for local Ollama (`/api/chat`, `/api/tags`) |
| `negotiate.py` | Ranks `CandidateSlot`s for a `HangoutRequest` |
| `prompts.py` | Ranking system/user prompts (JSON-only replies) |
| `config.py` | `OLLAMA_HOST`, `OLLAMA_MODEL`, timeouts, fallback |

Backend integration: `backend/services/agent_adapter.py` → `LocalAgentAdapter`
calls `agent.negotiate.rank_candidate_slots`.

## Prerequisites

1. Ollama listening on `http://127.0.0.1:11434`
2. Model pulled once while online, e.g. `ollama pull llama3.2:1b`

If you already have the zero-cloud voice stack under `~/local_llm`, start it with:

```sh
~/local_llm/scripts/phase1_chat.sh
```

## Configure

In `.env` (see `.env.example`):

```env
AGENT_ADAPTER=local
OLLAMA_HOST=http://127.0.0.1:11434
OLLAMA_MODEL=llama3.2:1b
AGENT_LOCAL_FALLBACK=1
```

`AGENT_LOCAL_FALLBACK=1` (default) returns the original candidate order if Ollama
is down or returns unusable JSON. Set to `0` to raise instead.

## Manual check

```sh
.venv/bin/python - <<'PY'
from datetime import datetime, timezone
from backend.models import HangoutRequest, CandidateSlot
from agent.local_llm import LocalLLM
from agent.negotiate import rank_candidate_slots

llm = LocalLLM()
print("available:", llm.is_available(), "models:", llm.list_models())

req = HangoutRequest(
    id="req-demo",
    requester_id="demo-zaynah",
    invitee_id="demo-daniella",
    start=datetime(2026, 10, 18, 10, 0, tzinfo=timezone.utc),
    end=datetime(2026, 10, 18, 18, 0, tzinfo=timezone.utc),
    allowed_activities=["coffee", "walk"],
    allowed_durations=[30, 60],
)
slots = [
    CandidateSlot(start=datetime(2026, 10, 18, 16, 0, tzinfo=timezone.utc),
                  end=datetime(2026, 10, 18, 17, 0, tzinfo=timezone.utc)),
    CandidateSlot(start=datetime(2026, 10, 18, 11, 0, tzinfo=timezone.utc),
                  end=datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc)),
]
print(rank_candidate_slots(req, slots, llm=llm))
PY
```

## Privacy

Do not send private preference notes, calendar event titles, or credentials to
another user's agent context. This lane only sees the hangout request fields and
candidate intervals the backend chooses to pass in.
