# Mutual API contract

Base URL: http://localhost:8000. Request/response definitions are in
[schemas.json](schemas.json), generated from backend/models.py. Sample records and
frontend payloads are in [examples.json](examples.json). See
[architecture](../docs/architecture.md) for implementation responsibilities.

## Identity and scope

Except /health, implemented endpoints require X-Demo-User-Id selecting a stored
demo user: demo-zaynah, demo-daniella, demo-kusum, or demo-mariann. The header is
a demo switcher, not production authentication. Server-owned IDs, caller identity,
status, and timestamps cannot be overridden in create inputs.

The MVP is person-first, two-person, and one-time availability. Activities:
coffee, meal, walk, study, concert. Durations: 30, 60, 90, 120 minutes. Optional
free-text location belongs to the request and is intended to carry into the
proposal unchanged; blank/null means location to be arranged.

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

## Implemented routes

| Method/path | Request schema | Success response | Rules |
|---|---|---|---|
| GET /health | none | 200 `{"status":"ok"}` | Implemented |
| GET /users | none | 200 PublicUser[] | Implemented; demo directory; valid demo identity required |
| GET /users/me | none | 200 User | Implemented; selected demo owner only |
| GET /users/{id}/schedule?start=...&end=... | aware query timestamps | 200 ScheduleResponse | Implemented; filter windows/calendar independently; validate aware range |
| POST /friend-requests | FriendRequestCreate | 201 FriendRequest | Implemented; sender from caller; known distinct recipient |
| GET /friend-requests | none | 200 FriendRequest[] | Implemented; caller is sender or recipient |
| POST /friend-requests/{id}/respond | FriendRequestRespond | 200 FriendRequest | Implemented; recipient only; server stamps responded_at |
| POST /friend-requests/{id}/remove | none | 200 FriendRequest | Implemented; either participant; accepted -> removed; replay idempotent |
| GET /users/me/social-windows | none | 200 SocialWindow[] | Implemented; owner only |
| POST /users/me/social-windows | SocialWindowCreate | 201 SocialWindow | Implemented; server generates ID and assigns caller; selected_friends requires accepted friends; invalid selections return 422 |
| PUT /users/me/social-windows/{id} | SocialWindowCreate | 200 SocialWindow | Implemented; owner only; selected_friends selections validated; invalid selections return 422 |
| DELETE /users/me/social-windows/{id} | none | 204 no body | Implemented; owner only |
| POST /hangout-requests | HangoutRequestCreate; optional Idempotency-Key | 201 HangoutRequest | Implemented; server assigns ID/requester; known distinct invitee |
| GET /hangout-requests | none | 200 HangoutRequest[] | Implemented; caller is requester/invitee; ordered by ID |
| GET /hangout-requests/{id} | none | 200 HangoutRequest | Implemented; participants only; missing/non-owned returns identical 404 |
| POST /hangout-requests/{id}/candidates | none | 200 CandidateOption[] | Implemented; participants only; both window policies and hard constraints enforced |

| POST /hangout-requests/{id}/proposals | ProposalCreate; optional Idempotency-Key | 201 Proposal | Participants only; fresh candidate validation; manual submit records caller approval; invalid/stale plan 409; inherited location |
| GET /hangout-requests/{id}/proposals | none | 200 Proposal[] | Participants only; ordered by ID; missing/non-owned request returns identical 404 |
| GET /proposals/{id} | none | 200 ProposalResponse | Participants only; missing/non-owned 404; stored approval decisions included |

| POST /proposals/{id}/approvals | ApprovalCreate | 200 ProposalResponse | Participants only; server identity/time; same decision replay safe; changes or new decisions on closed plans return 409 |

| POST /proposals/{id}/calendar-event | none; required Idempotency-Key header | 201 CalendarEventResponse; replay 200 | Participants only; both approvals, final availability check, durable claim and result |

| GET /hangout-requests/overview | none | 200 HangoutOverview[] | Caller’s requests and proposal/approval summaries only; consistent read snapshot |
| POST /proposals/{id}/replan | none | 200 ProposalResponse | Either participant; cancel unscheduled active options for this request; preserve history; calendar-write uncertainty returns 409 |

## Planned routes (not available)

| Method/path | Request schema | Success response | Rules |
|---|---|---|---|
| PUT /users/me/settings | UserSettings | 200 User | Owner only; validate selected friend relationships |
| POST /hangout-requests/{id}/negotiate | none | 201 Proposal | Explicit user action; backend coordinates agents and validates result; 409 if no match |

OAuth routes belong to the calendar lane and are not wired in this checkout.
No GET /users/{id}/friends endpoint exists; accepted relationships are available
through the caller's friend-request history and the public user directory.

## Permissions and social windows

Only owners may manage windows; update/delete returns identical 404 responses
for missing and non-owned IDs. PUT replaces editable fields and preserves ID and
owner. DELETE returns 204 without JSON and has no undo. Re-running the seed can
restore missing fixture windows, while preserving existing edits.

Audiences are private, community, friends, selected_friends. Community requires
matching simulated membership. Friends requires a current accepted relationship
in either direction. Selected friends requires both explicit selection and that
relationship. Creation/edit validates every selection: self, unknown, pending,
declined, or removed users cause 422 without writing changes. Old windows may
retain stale IDs, but those people no longer qualify for friend-based access.
The demo selected-friend picker uses accepted relationships and preserves saved IDs during editing. Revoked friends are flagged for removal before saving.

Calendar sharing defaults to private and is independent of window visibility.
Calendar free time alone never grants social availability. Browsing and matching
must enforce window audiences independently; agents cannot grant permissions.

## Friend request lifecycle

POST creates pending with a server ID, sender, and UTC timestamp. Self-request:
422; missing recipient: 404; pending/accepted pair in either direction: 409.
GET returns only the caller's incoming/outgoing history. Only the recipient may
respond: others get 403, missing request 404, invalid input 422, and conflicting
finalized decisions 409. Repeated identical decisions preserve result/time.

Accepted establishes friendship. Either participant may remove that exact record:
accepted -> removed, retaining the original acceptance time. Repeated removal is
idempotent; pending/declined removal returns 409. Removed cannot be reopened via
respond. Reconnecting requires a new request and acceptance. Replaying removal
against an old ID cannot affect a newer friendship. There is no removal timestamp.

## Schedule browsing

The URL ID selects the owner; the header identifies the viewer. start/end are
required aware query timestamps with end > start. Owners see their own private
and matching-only windows; other viewers see only visible windows whose audience
allows them. Return PublicUser and SharedSocialWindow projections, never private
settings or selected-friend lists. Clip intervals to [start,end), omit empty
intersections, and sort chronologically.

Calendar browsing denial returns calendar_busy=null without calling the adapter;
authorized ranges with no conflicts return []. Only the owner's start/end busy
blocks are exposed. Recheck friendship eligibility after the calendar await.
Failures return generic 502 without raw adapter messages. Default calendar data
is simulated. Browsing displays both sources rather than subtracting conflicts.

## Hangout requests and candidates

Creation records intention without guaranteeing a match or requiring friendship.
Requester/record IDs come from the backend. Self/invalid choices: 422; unknown
invitee: 404. Multiple requests between a pair are allowed. Listing returns the
caller's incoming/outgoing requests ordered by ID; query user_id cannot override
identity. Individual access returns identical 404 for missing/outsider requests.

POST candidates has no body and uses the saved request. Returns 200 CandidateOption[]
or [] for no match. Each option has exactly one eligible activity, a maximal free
interval, and sorted fitting request durations. It is not an exact proposal.
Both users' activity/duration hard constraints and window audiences apply.
Eligible matching-only windows may participate. Soft preferences are reserved for
agents and never appear in this response.

The backend privately checks both calendars even if calendar browsing is disabled,
but skips reads if windows/constraints already rule out any match. Busy conflicts
are subtracted, intervals clipped, and settings/windows/friendships refreshed after
adapter calls. Failures return 502, not free time. No inference, proposal, approval,
or event creation happens in the candidates operation. Groups are not supported.

## Proposal lifecycle

Proposal creation, viewing, and approval decisions are implemented. Mock calendar finalization is implemented; Google integration remains separate. A proposal must select a request-allowed
activity and exact allowed duration entirely within valid activity-specific
availability. Location carries over from the request. Backend validates agent or
manual output against current constraints and permissions.

Manual POST proposals atomically record the submitting caller’s approval of the
exact plan. Internal agent recommendations record no approvals. A proposal stays
pending until the other participant responds. Pending -> approved only after both distinct participants approve the same
immutable plan. Either decline closes it. Cancelled proposals are also closed and hidden in the demo. Another suggestion or changed plan
requires a new proposal and fresh approvals. Repeated same decisions on the agreed proposal are
idempotent; changing recorded decisions returns 409. Once a request has an
approved or scheduled proposal, new proposals and decisions on competing options
return 409. The check and write share a transaction so only one option can win.
Declined and competing records remain available through the participant-only API
for history; the demo hides declined options and shows only the agreed option.

Before event creation, recheck permissions, constraints, approvals, and free/busy.
Finalization uses a durable per-proposal claim; concurrent attempts return 409.
Idempotency-Key accepts 1–128 ASCII letters, digits, underscores, or hyphens.
Keys cannot be reused for other proposals. Completed results replay with 200,
even with a new key, without contacting the adapter. Successful finalization
stores the event ID and scheduled status atomically. Calendar failure returns a
generic 502 and leaves the plan approved/retryable. Stale availability returns 409.
No database transaction spans an external call. Crashed claims can be reclaimed
after five minutes; adapter writes must deduplicate a stable proposal-derived key.
The default mock simulates event creation; no Google event or invitation is sent.
Real integration must also reconcile ambiguous provider success (including excluding
an already-created event from its own conflict check) before claiming full recovery.

## Integration boundaries

CalendarAdapter exposes async get_busy(user_id, search) and
create_event(proposal, participant_ids, idempotency_key). The default dependency
in backend/dependencies.py returns a fixture-backed MockCalendarAdapter. Override
that dependency for Google integration/tests. It never exposes OAuth tokens or
calendar metadata through schedule responses.

AgentAdapter exposes evaluate(request, candidates). MockAgentAdapter preserves
input order; LocalAgentAdapter calls the teammate-owned Ollama ranker. Local
ranking is implemented, but no negotiation route invokes it. Zero/one candidate
skips inference; fallback returns input order on errors by default. It does not
yet handle private per-user contexts, activity-aware choices, counteroffers, or
no-match negotiation. Coordinate that contract with the agent owner before wiring.
Only permitted proposals should pass between personal contexts, never raw private
notes. Backend validation and human approvals remain authoritative.

## Errors

| Status | Meaning |
|---|---|
| 401 | Missing/unknown demo identity |
| 403 | Non-recipient/non-participant friendship action |
| 404 | Missing record; also used to conceal non-owned windows/requests/proposals |
| 409 | Duplicate active relationship, conflicting state, or invalid/stale proposal |
| 422 | Malformed inputs, invalid selections, or self-request |
| 502 | Calendar lookup failed |

Explicit business errors use {"detail":"message"}. FastAPI/Pydantic input errors
use {"detail":[{"loc":["body","field"],"msg":"...","type":"..."}]} with optional
diagnostic fields. Never return private notes, calendar metadata, or credentials.
Planned negotiation/event routes may use 409 for no match or stale calendar conflicts.

## Fixtures and schema updates

Fixtures describe Zaynah/Daniella as accepted friends, a pending Mariann request,
and Kusum as a community viewer. They include audience-specific schedule examples.
The seed inserts only users/windows, not those relationships or hangout records;
establish friendships interactively to reproduce friend-only responses. Example
preferences/schedules are fictional, and busy intervals are simulated.

After editing models, run `.venv/bin/python -m backend.scripts.export_schemas`.
Keep models, generated schemas, API contract, and examples aligned. Endpoint
availability is recorded in the two route tables above.

## Retry and replan behavior

Request and manual proposal creation accept an optional Idempotency-Key using the
same 1–128 character format as calendar finalization. Receipts bind actor, operation,
and validated payload; changed input or another operation with the same key returns
409. Identical retries return the original creation response without creating a
second record or approval. Fetch the overview to see its current state afterward.
The demo retains pending retry keys in sessionStorage as hashes/keys, without form
contents; confirmed successful responses clear the client key.

Replan closes the selected unscheduled option and all pending/approved alternatives
for that request as cancelled, preserving approvals. Repeating cancellation is safe.
Replacement proposals need fresh approvals. Scheduled events, active calendar claims,
and attempts that might have reached the provider block replan. A failed availability
check before any provider write permits replan. Migration marks old calendar attempts
conservatively as possibly written. Changing request constraints creates a new request;
the demo explicitly labels this action rather than modifying approved history.

The default demo adapter includes completed demo-event bookings in both participants’
free/busy results. The standalone MockCalendarAdapter remains fixture-only for tests.
