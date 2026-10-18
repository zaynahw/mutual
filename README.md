# Mutual

Mutual helps friends turn “we should hang out” into a plan. Personal agents are
intended to negotiate comfortable options using explicit social availability,
preferences, and boundaries. Both people must approve before an event is created.

## Run locally

Requires Python 3.10+ and Node 20.19+ or 22.12+ (Node 22.6+ for frontend tests).

From the repository root:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env
python -m backend.seed
uvicorn backend.main:app --reload --port 8000
```

In another terminal:

```sh
cd frontend
npm ci
npm run dev
```

Open [the demo panel](http://localhost:5173) or
[interactive API docs](http://localhost:8000/docs).
Root `.env` is a template and is not automatically loaded. Set backend variables
in the shell; set `VITE_API_BASE_URL` in the shell or `frontend/.env.local`.
CORS permits the default frontend origin, `http://localhost:5173`.

## Current capabilities

- SQLite-backed demo profiles and social-window create/read/edit/delete.
- Friend requests, accept/decline, removal, re-adding, and relationship history.
- Audience-filtered schedules with independently controlled calendar sharing.
- Hangout request creation/retrieval and deterministic activity-specific candidates.
- A local Ollama time-slot ranker, callable through its adapter but not yet wired
  to a negotiation route. See [agent setup](agent/README.md).

The current frontend is an integration panel for profiles, friendships, and owner
windows. Selected-friends controls, shared schedule browsing, requests, and
candidates are not connected to this panel yet; use the API docs for those routes.
The default calendar dependency uses simulated busy intervals. Google OAuth and
real event creation are not wired in this checkout. Separate agent contexts,
negotiation, proposal/approval routes, and the calendar-sharing settings update
route remain unfinished. Existing models/contracts describe these planned parts.

## Demo data and database

The seed creates four labeled demo users (Zaynah, Daniella, Kusum, Mariann) and
five social windows. Preferences and schedules are fictional. It inserts missing
records, preserves edits, and does not seed friendships, requests, or proposals.

SQLite lives in ignored `backend/mutual.db`. To create/upgrade tables without
seeding, run `.venv/bin/python -m backend.database`. Set `MUTUAL_DATABASE_PATH` in
the shell to override the file (parent directory must exist). Re-running the seed
restores missing fixture windows but does not remove old records.

`X-Demo-User-Id`, such as `demo-zaynah`, selects the caller. This is a test
switcher, not production authentication; do not use it to protect real user data.

## Verify

```sh
.venv/bin/python -m pytest
cd frontend
node --experimental-strip-types --test tests/*.test.mjs
npm run build
```

After editing Pydantic models, regenerate JSON Schemas from the repository root:

```sh
.venv/bin/python -m backend.scripts.export_schemas
```

## Project references

- [Architecture and code map](docs/architecture.md)
- [API contract and implementation status](contracts/api.md)
- [JSON Schemas](contracts/schemas.json) and [demo examples](contracts/examples.json)
- [Ownership, privacy, and coding guidelines](AGENTS.md)
