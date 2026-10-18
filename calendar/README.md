# Google sign-in and Calendar setup

The app has two explicit backend modes. `MUTUAL_MODE=demo` keeps the four fictional
profiles and simulated calendars. `MUTUAL_MODE=google` requires a real signed-in
session and uses real Google Calendar reads/writes. Demo identity headers do not
work in Google mode. This remains a local hackathon MVP, not a deployment guide.

## 1. Create a Google OAuth web client

1. Open Google Cloud Console and select or create a project.
2. Enable **Google Calendar API** in APIs & Services → Library.
3. Configure Google Auth Platform branding/audience (the OAuth consent screen).
   For testing personal accounts, choose an External audience and add **both
   Google accounts as test users** while the application is in testing.
4. Create an OAuth client ID of type **Web application**.
5. Add this exact authorized redirect URI:
   `http://localhost:8000/calendar/oauth/callback`.
6. Download the client JSON and save it as `backend/credentials.json` in this
   repository. The file is ignored by Git; do not commit or paste its contents.

Google's console labels can change. Official setup references:
[OAuth web application](https://developers.google.com/identity/protocols/oauth2/web-server)
and [Calendar API quickstart](https://developers.google.com/workspace/calendar/api/quickstart/python).

## 2. Configure the backend

Install `backend/requirements.txt`. Create a local `.env` from `.env.example` if
one does not already exist; preserve existing local settings. Set:

```dotenv
MUTUAL_MODE=google
GOOGLE_CREDENTIALS_FILE=/absolute/path/to/mutual/backend/credentials.json
GOOGLE_REDIRECT_URI=http://localhost:8000/calendar/oauth/callback
FRONTEND_URL=http://localhost:5173
COOKIE_SECURE=0
AGENT_ADAPTER=local
AGENT_LOCAL_FALLBACK=0
```

Alternatively set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET from the same client.
Generate a token-encryption key once:

```sh
.venv/bin/python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Put that value in `.env` as `MUTUAL_TOKEN_KEY=...`. Keep it stable: changing it
makes saved Google credentials unreadable. Keep `.env` and SQLite databases
private. The provider credentials are encrypted in SQLite; session cookies are
opaque and HttpOnly. COOKIE_SECURE=0 is for local HTTP development only.

Restart the existing backend with the environment file loaded explicitly:

```sh
source .venv/bin/activate
uvicorn backend.main:app --reload --env-file .env --port 8000
```

Start Ollama and the configured local model separately. Run the frontend:

```sh
cd frontend
npm run dev
```

Open http://localhost:5173/. The app should show **Continue with Google**, rather
than a demo identity picker. The separate backend testing page requires demo mode.

## 3. Test with two real accounts

Use separate browser profiles for the two accounts, or sign out of Mutual and
sign back in with the other account when testing sequentially.

1. Continue with Google as account A. A real Mutual profile is created or reused.
2. Choose **Connect Google Calendar**, selecting the **same account**. Sign-in and
   calendar permissions are separate consent steps. The second step requests
   free/busy access and calendar event access; grant both.
3. Repeat with account B.
4. Under Friends, send and accept a friendship between the two Mutual profiles.
5. As each person, either share specific social windows or explicitly enable
   calendar-free matching under Availability. Empty calendar time alone is not
   consent. Verify personal hours and profile timezone.
6. Send a free-text idea, confirm its interpretation, and let the agents negotiate.
7. Review the exact suggestion and approve once as each participant.
8. Choose **Add to Google Calendar**. This creates **one event on the requester's
   primary calendar** and sends a Google Calendar invitation to the other person.
   The invitee may still need to accept Google's invitation in their calendar.

Confirmed Mutual bookings count as busy for both people inside Mutual even while
Google's separate invitation is pending. The integration reads primary-calendar
free/busy and does not fetch event titles/descriptions. Other secondary calendars
are not included in this MVP. The earlier dedicated 'Mutual Hangouts' calendar
creation was intentionally replaced by primary-calendar writes, avoiding extra
calendar creation/listing permissions and keeping subsequent conflict checks
consistent.

## Runtime behavior

- Google identity is verified using the ID token (audience, issuer, nonce and
  verified email). OAuth uses browser-bound, expiring, single-use state and PKCE.
- Existing Google subjects map to the same Mutual profile; settings survive login.
- Personal Gmail accounts are not automatically marked as Georgia Tech students.
  A verified Google Workspace `hd=gatech.edu` claim grants that community label.
  Friendship matching works regardless of community.
- Google failures are unavailable/error states, never permission to assume free time.
- Provider event IDs are stable per proposal. Retries retrieve and validate an
  existing event, including recovery when an event was written but its response
  was lost. Both human approvals remain required before any new write.
- The app never falls back from real calendars to mock calendars. Agent fallback,
  when explicitly enabled, is independently labeled and still needs approvals.
- Sessions expire after seven days or sign-out. Google connection survives app
  restarts when the database and encryption key are retained.

If the callback fails, check the exact redirect URI, test-user membership, selected
Google account, configured credentials/key, and consent grants. Errors returned to
the browser deliberately omit provider tokens and authorization codes.
