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

| POST /hangout-requests/{id}/negotiate | none; required Idempotency-Key header | 200 NegotiationResponse | Participants only; agreed/no_match/exhausted; pending saved recommendation has zero human approvals; validated again after inference |

| PATCH /users/me/preferences | PreferenceNoteUpdate | 200 User | Owner only; updates only soft_preference_note; max 1000 characters; empty string clears |

## Planned routes (not available)

| Method/path | Request schema | Success response | Rules |
|---|---|---|---|
| PUT /users/me/settings | UserSettings | 200 User | Owner only; validate selected friend relationships |

OAuth sign-in and calendar-consent routes are implemented separately in backend/routes/auth.py; see the real Google identity section below.
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
in backend/dependencies.py returns a fixture-backed DemoCalendarAdapter. Override
that dependency for Google integration/tests. It never exposes OAuth tokens or
calendar metadata through schedule responses.

AgentAdapter exposes legacy evaluate(request, candidates) plus the integrated
negotiate(request, options, requester_ctx, invitee_ctx, max_rounds). LocalAgentAdapter
uses the teammate-owned Ollama negotiation loop; MockAgentAdapter uses a labeled
deterministic agreement. Separate owner contexts and structured pending offers
prevent private explanations from being forwarded. Backend validation and human
approvals remain authoritative. See Agent negotiation below for the public API.

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

## Agent negotiation

The backend supplies HangoutRequest, authorized CandidateOption[] and separate
OwnerPrivateContext values to AgentAdapter.negotiate. Each local model call gets
only its owner's context. Pending offers contain structured choices, never raw
reasons. Backend does not expose private notes, model explanations, or raw errors.

NegotiationResponse contains status (agreed/no_match/exhausted), source
(local_agent/demo_fallback/mock), optional saved Proposal, and structured turns
(actor_id, decision, optional activity/slot). Proposal.source also persists this
origin; existing and manual records default to manual. Public turns have no reason.
Any fallback turn labels the whole outcome demo_fallback. Source mock means no
inference. No candidates skip inference; no_match/exhausted save no proposal.

Agent-generated proposals require both humans to approve. Unlike manual creation,
calling negotiate does not count as human approval. Final recommendations must fit
both the original options and freshly generated candidates. A settled request or
stale recommendation returns 409. Inference failures/120-second total timeouts
return a generic 502 with manual selection still available. The round budget is
read from AGENT_MAX_ROUNDS and capped at three review turns plus an opening offer.

Negotiation keys use the existing 1–128 ASCII character format. Actor-scoped
receipts save the original sanitized response in the same transaction as proposal
insertion, preventing duplicate proposals on retries. Use a new key for a new
negotiation; GET overview reflects subsequent human decisions. Live inference
requires AGENT_ADAPTER=local and running Ollama; default mock needs no model.

## Private preference notes

PATCH /users/me/preferences accepts {"soft_preference_note":"..."}. Identity is
selected by the demo header; user IDs and unrelated settings in the body are
rejected. The update reads current profile JSON and changes only that field in a
transaction. Public profiles/schedule projections continue to omit notes. New
negotiations load the saved owner note; existing proposals and approvals do not
change. Notes guide choices among valid candidates and never override hard rules.
The full UserSettings update route remains planned; this endpoint is intentionally
limited to the note. Demo UI editor is under My profile.

### Natural-language requests (optional, confirmed before sending)

The existing manual request API remains available. The new demo path is:
`interpret → owner reviews → send → negotiate → both approvals → calendar event`.

| Endpoint | Body | Response |
| --- | --- | --- |
| PATCH /users/me/matching | MatchingSettings | 200 User |
| POST /hangout-intents/interpret | HangoutIntentCreate | 200 HangoutIntentDraft |
| GET /hangout-intents/{id} | none | 200 HangoutIntentDraft, owner only |
| POST /hangout-intents/{id}/send | none | 200 HangoutRequest, owner only; repeat returns same request |

Example interpretation input:
```json
{"invitee_id":"demo-daniella","days":["2026-10-19","2026-10-21"],"message":"I prefer morning coffee or a walk"}
```
Dates must be distinct, up to seven, within today through 14 days ahead in the
requester's timezone. Recurring weekdays are not supported. Input selects an
accepted friend. Interpretation returns an owner-only draft, a labeled source
(`local_agent`, `mock`, `demo_fallback`), and `IntentInterpretation`: activities,
allowed_durations, preferred_periods, earliest/latest local HH:MM or null, and a
clarification question or null. The original message stays private. Explicit supported clock limits are compiled deterministically; the model
interprets the broader message. Model output may still be semantically wrong: the owner reviews before sending.
Clarifications block sending; edit and interpret again. Invalid dates/inputs use
422; unavailable inference uses a generic 502. Missing/another owner's drafts use
404; revoked friendship, stale timezone/dates, or unresolved clarification use 409.

Sending compiles timezone-aware `search_windows` for exactly the selected dates
and sets server-owned `origin=intent`. It creates no proposal, approval or event.
Use POST /hangout-requests/{id}/negotiate next. Selected dates are never expanded
to include intervening days. Ambiguous/nonexistent required clock times at DST
transitions are rejected. Past times are excluded; today's starts round forward
to a five-minute boundary so inference and fresh checks can share a stable start.

MatchingSettings defaults to `{"mode":"social_windows","start_hour":9,"end_hour":21}`.
Calendar-guided mode is explicit opt-in, limited to accepted friends and personal
hours (integer start 0–23, end 1–24, end greater than start; timezone from profile).
It uses calendar-free time instead of detailed social windows. Both users' activity
and duration boundaries still apply. Confirming one's own natural request grants
request-scoped matching within one's personal hours; the recipient still needs
calendar-guided opt-in or authorized social windows. Browsing visibility remains
separate. Changing matching settings does not broaden calendar browsing access.
The requester's raw message and flexible period preferences go only to their own
agent; shared requests and the other agent never receive the message. Manual
requests default to origin=manual and retain the existing social-window behavior
unless a user has opted into calendar-guided matching.

### Real Google identity and calendar mode

`MUTUAL_MODE=demo` accepts labeled demo headers only. `MUTUAL_MODE=google` rejects
those headers and authenticates an opaque HttpOnly `mutual_session` cookie. All
session-authenticated writes require Origin matching FRONTEND_URL. The frontend
uses credentials-included requests; CORS permits only that explicit origin.
Provider tokens never appear in browser JSON. Demo and real profiles are separated
in the directory. UserId supports `demo-...` and `user-<32 lowercase hex>`;
`is_demo` is boolean and community may be null (unverified membership).

| Endpoint | Request | Response |
| --- | --- | --- |
| GET /auth/status | none | AuthStatus: mode, configured, authenticated, owner User or null, calendar_mode, calendar_connected |
| POST /auth/google/start | AuthStart: purpose `login` or `calendar`, timezone | authorization_url; sets HttpOnly OAuth browser-binding cookie |
| GET /calendar/oauth/callback | Google code/state or error | 303 to configured frontend with auth=success/failed |
| POST /auth/logout | none; trusted Origin | 204; revokes session and clears cookie |

Sign-in creates/reuses the account from a verified Google subject, never a client
user_id. Calendar linking requires the current signed-in user and the same Google
subject, with both free/busy and events scopes granted. OAuth state expires after
ten minutes and is browser-bound and single use; code exchange uses PKCE. Google
credentials and pending OAuth data are encrypted with MUTUAL_TOKEN_KEY in SQLite.
Do not expose the local demo mode as authentication for real data.

In Google mode calendar creation writes to the requester's primary calendar with
both participants as attendees and sendUpdates=all. A stable Google event ID and
validated recovery prevent duplicate writes. Free/busy errors fail closed. Local
confirmed real bookings supplement Google's primary-calendar results so a pending
invite cannot leave the invitee double-bookable in Mutual. No event titles or
other event details are exposed through schedule responses.

### Saved public exchange

`GET /hangout-requests/{id}/negotiation` returns the latest sanitized
`NegotiationResponse`, or `null` before a run. Requires request participation;
unauthenticated callers receive 401 and other users receive 404. Reads existing
idempotency receipts without invoking inference or creating plans. The embedded
proposal is a negotiation snapshot; use overview for current approvals/status.

Responses add optional `candidate_count` (eligible option records, not unique
slots) and `outcome_code`: `no_eligible_options`, `no_new_options`, `agents_no_match`, `round_limit`,
or null. Zero-option runs skip inference. Codes do not disclose another
participant's private constraints or the exact restriction excluding a plan.
Old receipts may omit these fields.

Subsequent negotiations exclude exact activity/start/end combinations already
proposed for that request, including declined plans. Alternatives include starts
at 30-minute offsets inside currently authorized free intervals. The model sees
at most 48 new exact choices per run; all output is revalidated against fresh
availability. `no_new_options` means eligible intervals exist but no unseen choice
remains on this search grid. Idempotent retries still replay their original result.

`POST /hangout-requests/{id}/negotiate?variation=different_time` excludes every
previously suggested start instant, across activities and durations. The default
`variation=any` excludes only exact prior plans. Unknown variations return 422;
the idempotency key binds the variation so a retry cannot change its meaning.
Both modes preserve existing proposals and require fresh human approvals for new
ones. This is request-specific feedback and does not change saved preferences.

## Shared availability board

`GET /availability-board?start=...&end=...` requires authentication and a timezone-aware
range of at most 14 days. It returns `AvailabilityCard[]`, ordered by start, owner,
and window ID. Each card contains a public owner, a clipped shared window, and
its audience label. Private windows, matching-only windows, expired windows,
unauthorized audiences, and profiles in the other demo/real mode are excluded.
No provider calendar is read; publishing availability is not a free/busy guarantee.
Current friendship and community membership determine audience access.

The Community UI lists seven days, publishes through the existing social-window
API, and routes accepted friends into interpretation review with a prefilled day,
activity, and same-day time range. Other members can send/review a friend request
first. Existing approval and scheduling checks remain authoritative. This is
availability discovery, not event RSVP or multi-person negotiation.


### Community membership and named shared windows

`PATCH /users/me/community` accepts only `{ "community": "georgia_tech" }` or
`{ "community": null }`. It modifies only the authenticated owner's membership.
For this hackathon this is an open, self-selected community, not verified student
status. Friends-only policies still require accepted friendship. Leaving revokes
access to community-only windows, including later scheduling of joined plans.

Social-window create/update and viewer projections include optional `title`
(maximum 100 characters), for example a concert artist. It is explicitly
published social content, never a provider calendar event title.

### Request to join a shared window

`POST /availability-board/{owner_id}/{window_id}/join` accepts `ProposalCreate`
(activity and exact slot) and a required payload-bound Idempotency-Key. Returns
201 `HangoutOverview` with one pending manual proposal and zero human approvals.
Friends-only windows require friendship; community windows require current
membership. Private or matching-only windows are not joinable. Unauthorized
windows are concealed with 404; invalid/changed availability yields 409; provider
failure yields 502 without saving partial requests. No agent is invoked for an
exact join request. Sender consent is limited to the chosen interval within
personal hours. Both calendars, activity/duration boundaries, source-window
visibility, and current audience permissions are enforced before persistence.

The request and proposal are inserted atomically with a retry receipt. The
server-only request fields `join_window_id` and `join_window_title` preserve the
source and its named activity context; client request-creation bodies reject
these fields. Final scheduling rechecks the source even if its owner has enabled
calendar-guided matching. Withdrawing the window, changing its title, revoking
friendship/community permission, or new conflicts blocks scheduling. Each join
request is a two-person plan; multiple joiners are not a multi-attendee RSVP event.
