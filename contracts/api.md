# Mutual API contract (v0 foundation)

Only `GET /health` is implemented. All other routes below are planned, not available. Base URL: http://localhost:8000. JSON bodies; timestamps use ISO 8601 with explicit offsets. Intervals are half-open `[start,end)` and require end > start. Unknown model fields are rejected.

## Identity and permissions

Future demo routes use `X-Demo-User-Id: demo-alex` or `demo-sam`, clearly labeled demo identities, never production authentication. Backend resolves identities from its demo registry, rejects unknown IDs, and owns all authorization and validation. IDs in payloads do not establish authority. Users may read/change their own settings only. Availability requires explicit owner permission; calendar free time alone is insufficient. Do not return raw busy intervals, boundaries, or private preferences to the other participant or their agent.

## Endpoints

| Method and path | Request JSON | Response JSON | Access |
|---|---|---|---|
| GET /health | none | 200 `{"status":"ok"}` | public; implemented |
| GET /users/me | none | 200 User | current demo user |
| PUT /users/me | User | 200 User | ID must equal current user; backend validates visibility targets |
| PUT /users/me/social-windows | `{"windows":[SocialWindow]}` | 200 same shape | all user_id values must equal current user; replace atomically |
| GET /users/me/social-windows | none | 200 `{"windows":[SocialWindow]}` | owner only |
| POST /hangout-requests | HangoutRequest | 201 HangoutRequest | requester must equal caller; distinct known invitee; check visibility |
| POST /hangout-requests/{id}/candidates | `{}` | 200 `{"candidates":[CandidateSlot]}` | participants only; both visibility permissions required |
| POST /hangout-requests/{id}/proposals | `{"slot":CandidateSlot}` | 201 Proposal | participant; backend generates ID and validates exact duration, availability, permissions, boundaries |
| GET /proposals/{id} | none | 200 `{"proposal":Proposal,"approvals":[Approval]}` | participants only |
| POST /proposals/{id}/approvals | `{"decision":"approve"}` or `{"decision":"decline"}` | 200 `{"proposal":Proposal,"approvals":[Approval]}` | caller must be a participant; server stamps identity and time |
| POST /proposals/{id}/calendar-event | `{}`; `Idempotency-Key` header required | 201 `{"proposal_id":"proposal-demo-1","event_id":"demo-event-proposal-demo-1"}`; replay 200 same | both approvals required; participant only |

Busy intervals come from the internal CalendarAdapter; there is no client endpoint for sharing raw calendar data. OAuth endpoints belong to the calendar lane and will be specified with that integration.

## JSON schemas

The canonical executable JSON Schemas are in `schemas.json`, generated from backend/models.py (Pydantic). Each named entry is a full JSON Schema including any nested definitions. The route table defines wrapper object schemas; all wrapper fields shown are required, with no additional properties. `examples.json` contains validated sample records.

| Model | Fields |
|---|---|
| User | id (demo-*), display_name, is_demo (true), timezone (display hint), availability_visible_to (user IDs), activity_preferences (strings), boundaries (strings) |
| SocialWindow | user_id, start, end |
| BusyInterval | user_id, start, end |
| HangoutRequest | id, requester_id, invitee_id, activity, duration_minutes (integer 1–1440), start, end (search bounds) |
| CandidateSlot | start, end |
| Proposal | id, request_id, slot (CandidateSlot), status (pending/approved/declined/scheduled; default pending) |
| Approval | proposal_id, user_id, decision (approve/decline), decided_at |

Backend must validate referenced users/requests, display timezone names, ownership, permissions, and relationship invariants in the service layer. Pydantic structural validation alone is insufficient. CandidateSlot means a maximal free interval in the candidates response; a proposal must select a slot of exactly the requested duration within one candidate.

## Approval and event lifecycle

Proposals are immutable. Changes require a new proposal and fresh approvals. Pending becomes approved only when both distinct participants approve; any decline makes it declined. Approved becomes scheduled only after successful event creation. Repeated same decisions are idempotent; conflicting decisions on finalized proposals return 409. Serialize finalization, recheck permissions and free/busy, and bind idempotency keys to the proposal/payload. Adapter failures must not mark scheduled; retries must avoid duplicate external events.

## Errors

Planned errors use `{"detail":"message"}`: 401 missing/unknown demo identity, 403 denied visibility/ownership, 404 missing record, 409 stale/conflicting proposal or calendar conflict, 502 integration failure. Validation errors use FastAPI's 422 `{"detail":[{"loc":["body","field"],"msg":"...","type":"..."}]}` format (additional diagnostic fields may appear). Never include tokens or private calendar contents in errors.

Persistence and these service-level checks are planned work, not implemented by the health-only scaffold.
