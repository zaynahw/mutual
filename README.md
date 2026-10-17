# Mutual

Hackathon foundation for two personal agents negotiating mutually comfortable hangouts. Explicit social windows, permissions, preferences, and boundaries constrain calendar free time. Both people approve before calendar event creation.

## Setup and run

Requires Python 3.10+ and Node 20.19+ or 22.12+.

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env
uvicorn backend.main:app --reload --port 8000
```

In another terminal:

```sh
cd frontend
npm ci
npm run dev
```

Open http://localhost:5173. The health button calls http://localhost:8000/health. Swagger docs: http://localhost:8000/docs. CORS permits the default Vite origin only.

Set VITE_API_BASE_URL in the shell or frontend/.env.local to override the API URL. Root .env is a configuration template; backend adapter selection and OAuth loading are not wired yet.

## Verify

```sh
.venv/bin/python -m pytest
cd frontend
npm run build
```

## Scope

frontend/ contains React, TypeScript, Vite, and Tailwind. backend/ contains health, Pydantic models, interval intersection, and adapter protocols/mocks. calendar/ and agent/ reserve teammate lanes. contracts/ defines planned endpoints and demo fixtures; tests/ checks the foundation.

Only GET /health is implemented. Business routes, scheduling UI, production authentication, OAuth, local model, and calendar writes are future lane work. Initial SQLite tables, connection handling, and user/window persistence helpers are available. Real adapter stubs raise NotImplementedError; the mock calendar stores demo event IDs in memory.

## Initial SQLite setup

Create the empty `users` and `social_windows` tables:

```sh
.venv/bin/python -m backend.database
```

This creates `backend/mutual.db`, which Git ignores. Running the command again
preserves existing records. It does not seed demo data or connect API routes.
Set `MUTUAL_DATABASE_PATH` in your shell to use a different file; the parent
directory must exist. The module does not automatically load the root `.env`.

`backend/database.py` exposes `connect()` as a context manager: successful work
is committed, exceptions roll it back, and the connection always closes. Records
will be saved as validated model JSON with IDs and ownership in separate SQL
columns. SQLite enforces unique IDs and existing owners; callers must enforce
Pydantic validation, JSON/column consistency, and access permissions. This is
initial schema setup, not a migration system. Database tests use temporary files.

Scheduling returns maximal common free intervals meeting the duration. Future proposal logic selects an exact duration-sized slot, checks permissions and boundaries, validates model output, and requires both approvals before calendar creation.

Read AGENTS.md and contracts/api.md before changing shared interfaces.

## Shared model contract

The model contract now supports four demo users, interactive friend requests,
per-window community/friends/selected-friends visibility, independently controlled
calendar free/busy sharing (private by default), and bounded activity/duration
negotiation. These are validated schemas and examples, not implemented routes.

`backend/models.py` separates client input, private owner records, and public
responses. `contracts/api.md` documents planned routes and backend permission
rules; `contracts/examples.json` provides frontend payloads and viewer-specific
schedule examples. Old activity/duration request fields and blanket user
visibility fields have been replaced; consumers should follow the updated schemas.

Regenerate JSON Schemas after changing models:

```sh
.venv/bin/python -m backend.scripts.export_schemas
```

The existing agent adapter is a foundation mock; its final private-context and
negotiation input/output contract must be coordinated with the agent teammate.

## Internal persistence helpers

`backend/repositories.py` provides `save_user`, `get_user`, `list_users`,
`create_social_window`, and `list_social_windows`. Initialize the database first.
User saving inserts or updates by ID; window creation inserts only and rejects
an existing ID or nonexistent owner. Reads rebuild and validate Pydantic records.
These helpers return private owner data and do not enforce viewer permissions;
future services must filter and project results before returning them to clients.
No business API routes are connected to these helpers yet.

## Seed demo data

From the repository root, run:

```sh
.venv/bin/python -m backend.seed
```

This initializes the tables and inserts missing users and social windows from
`contracts/examples.json`. An empty database receives four users (Zaynah,
Daniella, Kusum, and Mariann) and five windows. Names label demo identities;
preferences and schedules are fictional sample data, not the team's real data.
A second run reports zero inserts and preserves edits to existing records.
Seeding does not delete old records or migrate renamed identities.

The seed validates records first, then inserts users and windows in one
transaction. If an insertion fails, all new records from that run roll back.
Set `MUTUAL_DATABASE_PATH` in the shell to target a different database file.
Friend requests, busy intervals, requests, and proposals remain JSON examples;
this command does not persist them, create accounts, or call Google Calendar.
