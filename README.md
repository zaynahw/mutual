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

Only GET /health is implemented. Business routes, scheduling UI, production authentication, OAuth, local model, calendar writes, and SQLite persistence are future lane work. SQLite remains the intended MVP database. Real adapter stubs raise NotImplementedError; the mock calendar stores demo event IDs in memory.

Scheduling returns maximal common free intervals meeting the duration. Future proposal logic selects an exact duration-sized slot, checks permissions and boundaries, validates model output, and requires both approvals before calendar creation.

Read AGENTS.md and contracts/api.md before changing shared interfaces.
