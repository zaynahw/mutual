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

GET /health, GET /users, GET /users/me, GET/POST /users/me/social-windows, and PUT/DELETE /users/me/social-windows/{id} are implemented. Other business routes, scheduling UI, production authentication, OAuth, local model, and calendar writes are future lane work. Initial SQLite tables, connection handling, and user/window persistence helpers are available. Real adapter stubs raise NotImplementedError; the mock calendar stores demo event IDs in memory.

## Initial SQLite setup

Create missing `users`, `social_windows`, and `friend_requests` tables:

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
The read-only user API routes use these helpers; owner window GET/POST routes also use these helpers.

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

## Demo user integration panel

Seed first with `.venv/bin/python -m backend.seed`, start the backend and frontend
using the commands above, then open http://localhost:5173. Select a demo user to
load the public directory and that owner's full settings from SQLite. Profile settings remain read-only; the social availability panel supports
creating, listing, editing, and deleting owner windows. This is a temporary integration view for the frontend lane. Switching
users cancels pending requests and hides the previous profile. Reload data retries
failed requests. The existing health button remains available.

Both user routes require `X-Demo-User-Id` with a seeded ID, such as
`demo-zaynah`. Missing or unknown IDs return 401. GET /users returns PublicUser
records; GET /users/me returns the selected owner's private User record. The
switcher allows acting as any demo user and is not real authentication. The local
CORS configuration permits the demo header from http://localhost:5173.

Example request (or use Try it out in http://localhost:8000/docs):

```sh
curl http://localhost:8000/users/me -H "X-Demo-User-Id: demo-zaynah"
```

## Owner social availability

The demo panel lists all windows belonging to the selected user and supports
creating one-time windows with activities, audience, and sharing mode. Start/end
inputs use the selected profile's timezone, independently of the browser timezone;
DST gaps or repeated times require choosing another time. Saved UTC timestamps
are displayed in the owner's timezone. New windows default to private. Selected
friends is disabled until friendship storage exists. Existing seeded windows
remain visible to their owner. Cross-user browsing and matching are future work.

Changing users resets the window form. If a save request was already received by
the backend before switching, it can still complete for its original owner;
cancelling a browser request does not undo a committed write.

Timezone conversion checks (Node 22.6+ with type stripping):

```sh
cd frontend
node --experimental-strip-types --test tests/time.test.mjs
```

## Edit or delete social windows

Each saved window has Edit and Delete controls. Edit fills the form in the
profile's timezone; Save changes persists the replacement and Cancel editing
leaves the record unchanged. Delete requires an inline confirmation. Both routes
enforce ownership and return 404 for missing/non-owned windows. Switching users
clears editing and confirmation state. Editing selected-friends windows remains
disabled until friendship validation exists; owner deletion is available.
Deletion has no undo. The seed command restores missing fixture windows if rerun.

## Frontend code organization

- `src/lib/api.ts`: shared request/error handling and typed endpoint functions.
- `src/lib/time.ts`: profile-timezone input conversion and formatting.
- `src/components/SocialWindows.tsx`: saved data, form state, and API actions.
- `src/components/SocialWindowForm.tsx`: form controls and validation messages.
- `src/components/SocialWindowList.tsx`: saved windows and edit/delete controls.

The form and list receive values and callbacks from SocialWindows; they do not
make network requests. Backend create/edit visibility checks share one helper
in `backend/routes/social_windows.py` until friendship enforcement is added.

## Friendship storage foundation

The `friend_requests` table stores sender/recipient IDs, status, and timestamps
as SQL columns. Foreign keys require existing users; checks reject self-requests
and inconsistent pending/answered states. A unique index treats both directions
as the same pair and permits only one pending or accepted request per pair.
Declined history may coexist with a new request. Pydantic and future service code
must validate aware timestamps and response ordering; SQL does not parse these
text timestamp fields. `backend/friendships.py` provides `are_friends(user_a, user_b)`, an
ordered-pair lookup that returns true only for an accepted request. It also
provides `create_friend_request(sender_id, recipient_id)` and
`list_friend_requests(user_id)` for pending creation and incoming/outgoing history.
These internal functions do not authenticate callers; future routes must derive
IDs from the selected identity. Duplicate/unknown-user SQLite errors propagate
to callers. `respond_to_friend_request(request_id, recipient_id, decision)`
allows the recipient to accept/decline atomically. Repeating the same answer
preserves its timestamp; changing a finalized answer is rejected. LookupError
means missing, PermissionError means non-recipient, and ValueError means an
invalid/conflicting decision. Friendship API routes and the demo panel are implemented; friendship seed
inserts are not connected yet. Run `.venv/bin/python -m backend.database` to add the
empty table to an existing database without replacing users or windows.

## Friend request API

All routes require a seeded `X-Demo-User-Id`. Use Swagger at
http://localhost:8000/docs to send `{"recipient_id":"demo-daniella"}` as Zaynah
with POST /friend-requests. Switch the header to demo-daniella and use GET
/friend-requests to find its ID, then POST /friend-requests/{id}/respond with
`{"decision":"accept"}` or `{"decision":"decline"}`. Only the recipient may
answer. Repeated same answers preserve the result; conflicting answers return
409. Pending/accepted pairs cannot have duplicate requests in either direction.
These routes do not yet affect cross-user schedule access or selected-friends
window editing, and the frontend now provides a demo friendship panel.

## Demo friendship panel

The Friendships panel uses the public user directory for names, excluding the
selected user from Add friend choices. Send a request, switch to the recipient,
and Accept or Decline. Pending and accepted pairs cannot be requested again;
declined history permits a new request. Incoming/outgoing requests, accepted
friends, and declined history are shown separately. Refresh requests loads changes
made in another browser tab. Updates disable actions until completion, report
errors, and reset on demo-user switching. An already-received write can complete
for the original user even if its browser request is cancelled while switching.

`src/components/Friendships.tsx` coordinates state and API actions;
`src/lib/friendships.ts` determines active pairs without letting old declined
history hide a newer request. `src/lib/api.ts` reuses the shared request helper.
These relationships are real SQLite demo records, but other-user schedule
filtering and selected-friends controls remain future work.

Run all frontend logic and timezone checks with Node 22.6+:

```sh
cd frontend
node --experimental-strip-types --test tests/*.test.mjs
```

## Remove and re-add friends

Accepted friends have a Remove friend control with inline confirmation. Either
participant can remove that specific relationship using POST
/friend-requests/{id}/remove. Missing requests return 404, outsiders 403, and
pending/declined records 409. Repeating removal returns the same removed record.
The original acceptance timestamp is retained; a separate removal timestamp is
not recorded. Removed records stay in Relationship history. A new friend request
can be sent in either direction and must be accepted again. Replaying removal
of an old record cannot remove a newer friendship.

Run `.venv/bin/python -m backend.database` when upgrading an existing checkout.
Initialization transactionally rebuilds the old friend_requests table to permit
removed status, preserves all rows, and recreates its unique active-pair index.
New databases use the updated schema directly. Upgrade failures roll back the
friendship table changes. Future schema changes need their own explicit migration.
The API/schema and frontend recognize removed as inactive. Viewer permissions
will use current accepted friendships once schedule filtering is implemented.

## Audience permission helper

`backend/services/permissions.py` exposes `can_access(owner, viewer, policy)` for
trusted, backend-loaded User records. Owners always qualify; private excludes
others; community requires matching simulated community membership; friends
requires a currently accepted relationship; selected_friends additionally requires
explicit selection. Removal revokes friend-based eligibility on the next check
without removing community access. The helper does not cache grants.

This helper is not connected to schedule routes yet. It checks audiences only;
callers must separately hide matching-only windows from other users, validate
selected-friend settings, and project permitted response fields. The current
owner-only routes and frontend remain unchanged.

## Selected-friends window API

The backend now accepts selected_friends when all selected IDs are accepted
friends of the owner. Creation and editing reject self, unknown, pending,
declined, or removed users with 422, without changing saved data. Pydantic still
requires a nonempty unique list. Owners can change to a different audience to
clear old selections. Audience access checks also require current friendship,
so removing a friend revokes eligibility even if an old window retains their ID.
The frontend picker/edit restriction remains disabled until its integration;
use Swagger to exercise this backend feature. Shared schedule routes are next.
