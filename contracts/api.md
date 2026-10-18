# Mutual API contract — bounded negotiation MVP

`GET /health`, `GET /users`, `GET /users/me`, and GET/POST `/users/me/social-windows` and PUT/DELETE `/users/me/social-windows/{id}` are implemented. The send/list/respond/remove /friend-requests routes are also implemented. GET /users/{id}/schedule is also implemented. Every other route below is planned. Base URL: http://localhost:8000. JSON Schemas: [schemas.json](schemas.json). Validated four-user records and frontend payloads: [examples.json](examples.json).

## Agreed scope

Four labeled demo users; simulated Georgia Tech membership; interactive friend requests; one-time social windows; two-person hangouts; person-first requests. Activities: coffee, meal, walk, study, concert. Durations: 30, 60, 90, 120 minutes. Requests specify acceptable choices; agents may negotiate within them. Optional free-text location is copied from request to proposal without agent negotiation or venue validation. Blank/null means “Location to be arranged.” Declining closes a proposal; another suggestion requires an explicit action and fresh approvals.

## Model boundaries

- `User`: private owner record, including Preferences, HardConstraints, calendar sharing. Never return it from another person's profile endpoint.
- `UserSettings`: owner-editable settings; excludes ID, demo flag, and community membership.
- `PublicUser`: ID, display name, demo label, community only.
- `VisibilityPolicy`: private/community/friends/selected_friends. Only selected_friends accepts a nonempty selected_friend_ids list.
- `FriendRequest`: backend-owned sender, recipient, status, and times. Acceptance establishes a mutual friendship. Duplicate/reverse requests must not create duplicate relationships.
- `SocialWindow`: one-time interval, allowed activities, visibility, visible/matching_only mode. Private windows cannot match other users. Matching-only windows participate in authorized matching but never appear on another user's schedule.
- `BusyInterval`: internal calendar free/busy record, with no event metadata.
- `ScheduleResponse`: PublicUser, visible SharedSocialWindow records, and calendar_busy. `null` means calendar access is denied; `[]` means allowed with no busy intervals in the queried range. No selected friend IDs or private preference notes are exposed.
- `HangoutRequestCreate`: client search bounds, invitee, allowed activities/durations, optional location. HangoutRequest adds server-generated ID and caller-derived requester.
- `CandidateSlot`: pure interval output from intersection. CandidateOption attaches eligible activities/durations after service-layer checks. If activities differ across a time range, split the interval rather than attaching an activity valid for only part of it.
- `ProposalCreate`: selected activity and exact slot. Proposal adds ID, request ID, inherited location, and status. Duration is derived from the slot and must be one of the supported choices.
- `ApprovalCreate`: decision only. Approval adds caller-derived user ID, proposal ID, and server timestamp.

All timestamps are timezone-aware ISO 8601. Intervals are half-open [start,end); elapsed duration is calculated in UTC. Unknown fields and duplicate option values are rejected. Pydantic validates record structure, not authorization or database relationships. Full JSON request/response schemas use the named definitions in schemas.json; list responses are JSON arrays of the named model.

## Identity and permissions

`X-Demo-User-Id` selects demo-zaynah, demo-daniella, demo-kusum, or demo-mariann. This is a demo switcher, not production authentication. Resolve IDs through the registry, never trust a body ID as caller identity. Do not publicly deploy this mode as authenticated access.

Calendar sharing defaults to private and is independent of social-window visibility. Community requires matching simulated community membership. Friends requires an accepted relationship in either direction. Selected friends additionally requires the viewer's ID in the owner's selected list; backend validates these IDs are accepted friends and excludes self. Owners can access their own data. Viewers must never receive full User or internal busy records; project only authorized fields and clip returned intervals to query bounds.

Calendar read-sharing permission does not determine matching permission: backend may privately consult busy data to validate authorized social windows even when calendar browsing is disabled. Calendar free time alone never grants social availability. Each participant's window audience must permit the other participant. Hard constraints of both users restrict activities/durations; soft preferences guide agents only. Never forward one user's private notes to the other user's agent.

## Planned routes

| Method/path | Request schema | Success response | Rules |
|---|---|---|---|
| GET /health | none | 200 `{"status":"ok"}` | Implemented |
| GET /users | none | 200 PublicUser[] | Implemented; demo directory; valid demo identity required |
| GET /users/me | none | 200 User | Implemented; selected demo owner only |
| PUT /users/me/settings | UserSettings | 200 User | Owner only; validate selected friend relationships |
| GET /users/{id}/schedule?start=...&end=... | aware query timestamps | 200 ScheduleResponse | Implemented; filter windows/calendar independently; validate aware range |
| POST /friend-requests | FriendRequestCreate | 201 FriendRequest | Implemented; sender from caller; known distinct recipient |
| GET /friend-requests | none | 200 FriendRequest[] | Implemented; caller is sender or recipient |
| POST /friend-requests/{id}/respond | FriendRequestRespond | 200 FriendRequest | Implemented; recipient only; server stamps responded_at |
| POST /friend-requests/{id}/remove | none | 200 FriendRequest | Implemented; either participant; accepted -> removed; replay idempotent |
| GET /users/me/social-windows | none | 200 SocialWindow[] | Implemented; owner only |
| POST /users/me/social-windows | SocialWindowCreate | 201 SocialWindow | Implemented; server generates ID and assigns caller; selected_friends requires accepted friends; invalid selections return 422 |
| PUT /users/me/social-windows/{id} | SocialWindowCreate | 200 SocialWindow | Implemented; owner only; selected_friends selections validated; invalid selections return 422 |
| DELETE /users/me/social-windows/{id} | none | 204 no body | Implemented; owner only |
| POST /hangout-requests | HangoutRequestCreate | 201 HangoutRequest | Server assigns ID/requester; known distinct invitee |
| POST /hangout-requests/{id}/candidates | none | 200 CandidateOption[] | Participants only; both window policies and hard constraints enforced |
| POST /hangout-requests/{id}/negotiate | none | 201 Proposal | Explicit user action; backend coordinates agents and validates result; 409 if no match |
| POST /hangout-requests/{id}/proposals | ProposalCreate | 201 Proposal | Participant only; validates choices and slot; copies location from request |
| GET /proposals/{id} | none | 200 ProposalResponse | Participants only |
| POST /proposals/{id}/approvals | ApprovalCreate | 200 ProposalResponse | Caller must be participant; server supplies identity/time |
| POST /proposals/{id}/calendar-event | none; Idempotency-Key header | 201 CalendarEventResponse; replay 200 | Both approvals and final validation required |

Create-input schemas deliberately omit IDs, caller identity, status, and server timestamps. Window update/delete returns the same 404 for missing and non-owned records; other ownership-denied operations use 403. Creation of requests may precede finding a match; candidates can be empty. Calendar OAuth routes are deferred to the calendar lane.

## Proposal lifecycle and enforcement

Pending -> approved only when both distinct participants approve the same immutable plan. Either decline closes it; it cannot be reopened. A new suggestion creates a new proposal with zero approvals. Changed time/activity/location also requires a new proposal. Repeating the same decision is idempotent; changing a recorded decision returns 409 for this MVP. Friend-request responses follow the same repeated-versus-conflicting rule.

Before accepting a proposal or creating an event, validate request choices, both users' hard constraints, activity-specific social windows, audience eligibility, and busy intervals. Proposal interval must have one allowed duration and lie entirely inside valid activity-specific availability. Agents are advisory and cannot bypass these checks. Serialize finalization and bind idempotency keys to proposal/payload; integration failure must not mark scheduled or create duplicates on retry. Database constraints/transactions enforce participant uniqueness and state transitions.

## Integration boundaries

CalendarAdapter remains the internal async get_busy/create_event interface. Calendar sharing grants only projected busy blocks, never Google event details or OAuth tokens.

### Agent negotiation contract (agreed — agent lane)

`AgentAdapter.negotiate(...)` is the integration point for
`POST /hangout-requests/{id}/negotiate` (route still planned). Model output is
advisory; backend must revalidate options, hard constraints, windows, busy time,
and dual approvals before creating a Proposal.

**Input (backend → agent)**

- `HangoutRequest` (shared)
- `CandidateOption[]` already filtered by backend (activities/durations attached)
- `OwnerPrivateContext` for requester and invitee **separately** (never cross-send
  `soft_preference_note` between owners)
- `max_rounds` (default 3)

`OwnerPrivateContext`: `{owner_id, preferred_activities, soft_preference_note,
max_duration_minutes, timezone}` — see `agent/schemas.py`.

**Per-agent turn output**

```json
{"decision":"propose|counter|accept|no_match","option_index":0,"activity":"coffee","duration_minutes":30,"reason":"..."}
```

Validated into an exact `ProposalCreate` (`activity` + duration-sized `CandidateSlot`
starting at the chosen option's start). Agents cannot invent times outside options.

**Orchestration output (`NegotiationResult`)**

- `status`: `agreed` | `no_match` | `exhausted`
- `proposal`: `ProposalCreate` when agreed (backend adds id/location/status)
- `turns`: audit trail of each owner's `AgentDecision`
- `reason`: short summary

Two personal agents alternate: requester proposes, invitee reviews
(accept/counter/no_match), counters flip the pending offer, stop on agree,
no_match, or round budget. Set `AGENT_ADAPTER=local` for Ollama or `mock` for
deterministic first-fit. Details: `agent/README.md`.

## Errors

401 unknown/missing demo identity; 403 denied access; 404 missing record; 409 state conflict/no match/calendar conflict; 502 dependency failure. These use `{"detail":"message"}`. Validation errors use FastAPI 422 `{"detail":[{"loc":["body","field"],"msg":"...","type":"..."}]}` with optional diagnostic fields. Never include private notes, calendar metadata, or credentials in errors.

## Four-user demo

Zaynah and Daniella are accepted friends. Mariann has a pending request to Zaynah; accepting unlocks friends-only access. Kusum is a community member with no friendship to Zaynah. Zaynah has community, friends, and Daniella-only windows. Daniella also has a matching-only window. Fixtures include viewer-specific schedule projections to distinguish hidden calendar data from shared busy blocks. These projections illustrate the contract; permission filtering is not implemented yet.

## Regenerate schemas

Run `.venv/bin/python -m backend.scripts.export_schemas` from the repository root. Commit models, generated schemas, fixtures, and contract changes together after review. User read routes are implemented against SQLite. Other business routes remain planned. Seed the database before running user routes.

## Owner social-window implementation

GET and POST /users/me/social-windows are database-backed. Owner reads include
private and matching-only windows. Creation accepts all four audiences; selected_friends requires every selected
ID to be a currently accepted friend, excluding the owner. Invalid relationships
return 422. Existing seeded selected-friends windows remain readable.
The API requires offset-aware timestamps; the demo form converts from the owner's
IANA timezone to UTC and rejects DST gaps/repeated times. Cross-user schedule browsing and selected-friend write validation are implemented.
Activity-aware matching is not implemented yet.

## Owner window edits and deletion

PUT replaces editable fields but preserves the URL ID and caller ownership.
DELETE returns 204 with no body. Both SQL operations match ID and owner in one
statement; missing and non-owned IDs return identical 404 responses. Invalid
updates leave the stored record unchanged. Selected-friends edits require all selected IDs to remain accepted friends;
seeded selected-friends windows can still be deleted by their owner. There is no
undo for deletion. Re-running the seed restores missing fixture windows, while
preserving edits to existing records.

## Friendship endpoint behavior

POST /friend-requests creates a pending request for the caller. A self-request
returns 422, a missing recipient 404, and an active request/friendship in either
direction 409. Input cannot override sender, status, IDs, or timestamps.
GET /friend-requests returns only the caller's incoming/outgoing history.
POST /friend-requests/{id}/respond returns 403 for a non-recipient, 404 for a
missing request, 422 for a malformed decision, and 409 for changing a finalized
decision. Repeating the same answer returns the unchanged record and timestamp.
Acceptance is stored and available through are_friends; cross-user schedule
filtering is now implemented. Selected-friends write validation is implemented. The demo friendship UI is connected; fixture friendship seeding is not.

## Removing friendships

FriendRequest.status also permits removed, which retains responded_at from the
original acceptance. POST /friend-requests/{id}/remove requires either
participant's demo identity and an accepted record. It returns the removed
record, 404 if missing, 403 for a non-participant, or 409 for pending/declined
records. Repeating removal of the same record returns it unchanged. Removed
records never count as friendship and do not block new requests. Acceptance of
a new request is required to reconnect. Respond cannot reopen removed records.
Removal is scoped to the request ID, so replaying an old removal cannot affect a
new accepted relationship. Demo UI provides confirmation and relationship history.

## Selected-friend validation

POST/PUT owner social-window routes validate selected-friend relationships against
current SQLite state. Self, unknown users, pending, declined, and removed friends
are rejected with 422. Mixed valid/invalid selections reject the entire write.
Existing windows can retain stale IDs after removal, but the audience helper
requires a current accepted friendship and therefore denies those viewers.
Owners may change an old window to a different audience to clear stale selections.
The frontend selected-friend picker is not connected yet; use the API/Swagger.

## Unified schedule browsing

GET /users/{id}/schedule requires aware ISO start/end query values and the viewer's
X-Demo-User-Id header. The URL ID selects the owner; the header selects the viewer.
Missing/unknown identity returns 401, missing owner 404, invalid/missing queries
422. Returns ScheduleResponse with public User fields, projected social windows,
and separately authorized calendar_busy. Owners see their private/matching-only
windows; other viewers never see matching-only windows. Audience checks use the
current accepted friendship state. Intervals are clipped to [start,end), empty
intersections omitted, and results sorted chronologically. This is a browsing
projection, not a subtraction of calendar conflicts or agent candidate generation.

Calendar browsing denial returns calendar_busy=null without calling get_busy.
Authorized empty ranges return []. Only the owner's busy records are included;
no calendar metadata or user IDs are present in busy blocks. Adapter exceptions
return a generic 502, never their raw messages. Friendship eligibility is rechecked
after awaiting calendar results. The default dependency supplies simulated busy
intervals from examples.json; override backend.dependencies.get_calendar_adapter
for Google integration or tests. It uses the existing CalendarAdapter protocol.
No real Google calls or frontend changes are included in this endpoint work.
