# Mutual architecture

## Responsibilities and flow

The frontend calls the main FastAPI backend. The backend owns persistence,
identity resolution, permissions, deterministic scheduling, and eventual proposal
and approval state. Calendar and model integrations remain behind adapters.

```text
React frontend -> FastAPI -> SQLite
                         -> CalendarAdapter -> mock / future Google integration
                         -> AgentAdapter -> mock / local Ollama ranker
```

The agreed MVP is person-first and two-person, with one-time social windows.
Activities are coffee, meal, walk, study, concert; durations are 30/60/90/120
minutes. Location is optional free text and is not negotiated or venue-validated.
Group plans and activity-first discovery are later scope.

The implemented request flow is:

```text
Create hangout request -> load both profiles and permitted windows
                      -> check both calendars -> return valid CandidateOptions
```

The remaining flow is agent evaluation/negotiation -> validated exact proposal ->
two independent approvals -> final permission/conflict checks -> one calendar
event. The current local agent ranks plain time intervals; it does not implement
separate personal contexts, activity/duration compromises, or a no-match exchange.
Its default failure fallback returns the original slot order; disable fallback
when proving real inference. Coordinate agent changes with its owner.

## Code map

| Path | Responsibility |
|---|---|
| `frontend/src/demo/main.tsx` | Current demo entry point and identity selection |
| `frontend/src/demo/lib/api.ts` | Typed API calls and shared request/error handling |
| `frontend/src/demo/lib/time.ts` | Profile-timezone date input conversion |
| `frontend/src/demo/components/Friendships.tsx` | Friend request/history/removal UI |
| `frontend/src/demo/components/SocialWindows.tsx` | Owner window state and API actions |
| `frontend/src/demo/components/SocialWindowForm.tsx` | Form presentation |
| `frontend/src/demo/components/SocialWindowList.tsx` | Window list and edit/delete controls |
| `backend/main.py` | FastAPI app, CORS, router registration, health |
| `backend/models.py` | Pydantic domain, input, and response schemas |
| `backend/dependencies.py` | Demo identity, participant access, calendar injection |
| `backend/routes/` | HTTP endpoints and HTTP error mapping |
| `backend/database.py` | SQLite transactions, tables, friendship upgrade |
| `backend/repositories.py` | User and social-window persistence |
| `backend/friendships.py` | Relationship creation, responses, removal, lookup |
| `backend/hangouts.py` | Request insertion and retrieval |
| `backend/proposals.py` | Pending proposal insertion and retrieval |
| `backend/services/permissions.py` | Audience checks and selected-friend validation |
| `backend/services/schedule.py` | Permission-filtered schedule projection |
| `backend/services/scheduling.py` | Pure interval intersection and busy subtraction |
| `backend/services/candidates.py` | Activity-aware candidate generation |
| `backend/services/proposals.py` | Validate exact recommendations against fresh candidates and save pending plans |
| `backend/services/calendar_adapter.py` | Calendar protocol, mock, Google stub |
| `backend/services/agent_adapter.py` | Mock/local model adapter and factory |
| `agent/` | Teammate-owned local Ollama client and slot ranking |
| `calendar/` | Calendar integration ownership documentation |
| `backend/seed.py` | Repeatable insertion of missing fixture users/windows |
| `backend/scripts/export_schemas.py` | Generates contracts/schemas.json |
| `contracts/` | Shared API definitions, schemas, and example data |

## Data validation and persistence

Pydantic validates data shape, aware timestamps, supported choices, and local
record invariants. It does not create tables or establish authorization. Backend
logic checks relationships and caller permissions. SQLite enforces primary keys,
foreign keys, and relevant checks/unique indexes.

Users, social windows, hangout requests, and proposals store complete model JSON plus SQL
columns for IDs/ownership/participants. Save functions derive both from the same
object; readers rebuild through Pydantic. SQL does not enforce JSON/column
consistency. Friend requests store fields as separate columns for state queries.

`connect()` commits successful work, rolls back exceptions, and always closes.
Initialization creates missing tables/indexes and upgrades the original friendship
status constraint transactionally. That upgrade preserves rows and recreates the
active-pair index; future schema changes need explicit migrations too.

An accepted friend request establishes mutual friendship; no separate friendship
table is needed. Removal retains the record with status removed and the original
acceptance time. There is no separate removal timestamp. Only pending/accepted
pairs block another request. Same decisions/removals are idempotent, and replaying
an old removal cannot remove a newer accepted relationship.

Proposal storage requires an existing hangout request, unique proposal IDs, and
pending initial status. Multiple proposals per request are allowed. The local
database has a proposals table and a validation service. The service regenerates
candidates and requires the activity, exact duration, and entire proposed interval
to fit one valid option, then assigns an ID and inherits the request location.
No partial proposal is saved on invalid recommendations or calendar failure.
Participant routes enforce request ownership before creation and proposal ownership
before retrieval. Approvals and recommendation-source labeling are not implemented
yet; retrieval returns an empty approvals list. Final
calendar creation must recheck availability; saving a proposal is not a reservation.

Internal repository functions are not authorization boundaries. User records
contain private settings. Routes must project PublicUser for the directory and
verify participation before exposing requests. ParticipantRequest centralizes
that request check; ParticipantProposal checks the parent request for saved plans.
friendship_errors maps known friendship failures locally.

## Visibility and scheduling

Calendar availability and social availability are different. Calendar free time
does not imply interest in socializing. Each window has activities, an audience,
and visible/matching_only mode; calendar sharing has an independent policy.

Owner access is allowed. Other viewers qualify through community membership,
current accepted friendship, or both explicit selection and current friendship.
Removing a friend revokes friend-based access even if an old window retains their
ID; community access can still apply. Selected-friend writes reject self and
non-friends. All community membership is simulated for the demo.

Browsing hides matching-only windows from other people, clips both sources to the
query range, and returns public projections. calendar_busy=null means not shared;
[] means shared without conflicts. Denied calendar browsing never calls the
adapter. Internal matching can check busy intervals without calendar-browsing
permission when both users' social-window audiences authorize the match.

Candidate generation handles one activity at a time, intersects both users'
eligible windows, subtracts both busy sets, and filters durations against both
hard constraints. Options are maximal free intervals, not final meeting slots.
Matching-only windows are eligible internally. Settings/windows/friendships are
rechecked after calendar calls; failures return generic errors rather than free
time. Soft preferences are left for the personal agents.

## Privacy and integration boundaries

The default calendar dependency uses fixture busy intervals without storing them
in SQLite. Replace/override get_calendar_adapter for Google integration. Do not
expose calendar event titles, descriptions, locations, credentials, or raw errors.
Real OAuth/account mapping and event retry behavior require integration work.

Each future personal agent should receive only its owner's private context;
agent-to-agent exchange should contain limited permitted plans/counteroffers.
The backend must revalidate outputs and enforce two approvals of one immutable
proposal before writing an event. Model/schema presence does not mean these
planned services are implemented; route status is tracked in contracts/api.md.

## Testing and demo UI behavior

The backend demo has its own entry, frontend/demo.html, and lives entirely under
frontend/src/demo/. The main index.html/main.tsx entry is reserved for the product
frontend. Vite builds both pages; use /demo.html for backend testing.

Test setup in tests/conftest.py is function-scoped: database_path selects a
nonexistent file, initialized_database creates empty tables, and seeded_database
adds demo users/windows. Specialized adapter fixtures stay local. Tests never
need the developer's database, live Google access, or a live model.

The demo window form uses the selected user's timezone, not the browser's. It
rejects DST gaps/repeated times, resets on identity change, and confirms deletion.
Window deletion has no undo. The friendship panel confirms removal and supports
refreshing state from another tab. Cancelling a browser request does not undo an
already-received backend write. Selected-friends controls and new schedule/request
routes still need wiring into the final frontend design. The separate demo now
supports schedule browsing, request creation/listing, candidate generation, exact
manual proposal creation, and participant-only proposal lookup by ID.
