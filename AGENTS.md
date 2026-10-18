# Mutual architecture and ownership

Local MVP for a 24-hour Agents on Device hackathon.

- frontend/: UI owner; consume contracts, never authorize client-side.
- calendar/: Calendar teammate owns OAuth and Google Calendar integration.
- backend/: API owner owns validation, permissions, scheduling, proposals, approvals, and SQLite persistence.
- agent/: Separately owned local model and negotiation. Do not implement or replace the teammate's model. Integrate through backend/services/agent_adapter.py.
- contracts/: Shared interfaces; coordinate cross-lane schema changes.

## Privacy

Keep demo mode separate from real Google identity sessions. Demo IDs are not authentication; do not publicly deploy demo identity endpoints as authenticated services. Never commit tokens, secrets, personal calendars, or databases. Do not log private schedules. Calendar integrations should expose free/busy only, without event titles, descriptions, or locations.

Backend must enforce visibility before access and revalidate all agent output. Free calendar time alone does not grant social availability. Share only permitted candidate slots between personal agents; private boundaries stay with their owner's agent. Enforce activity preferences and explicit boundaries before proposals.

Both distinct participants must approve the same immutable proposal before a calendar event is created. Changes invalidate approvals. Recheck permissions and free/busy before creation; use transactional approval state and idempotent creation. Adapters are internal interfaces, never authorization endpoints.

## Guidelines

Use timezone-aware ISO 8601 timestamps, UTC comparisons, and half-open intervals. Keep scheduling deterministic and pure. Reject unknown fields in Pydantic models. Keep integrations mockable. Coordinate through protocols instead of editing other lanes unnecessarily. Add meaningful behavior tests; run pytest and frontend build before review. Do not commit or push until user review.

## Google integration

Real users use verified Google subjects and opaque HttpOnly sessions; never accept a user ID header as real authentication. Keep account/token storage in backend/accounts.py and OAuth routes separate from main.py. Encrypt persisted provider credentials using the configured stable key. Calendar services expose free/busy only, fail closed on provider errors, and use primary-calendar events with stable IDs and validated replay recovery. Never silently switch real accounts to mock calendars. Preserve both human approval checks. See calendar/README.md for local setup.
