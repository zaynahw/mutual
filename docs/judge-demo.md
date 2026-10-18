# Mutual: demo and pitch scope

## What this branch demonstrates

Mutual turns a request to spend time with a friend into a concrete suggestion.
Calendar free time is used only with social permission: shared social windows,
or explicit calendar-guided matching within personal hours. The sender confirms
matching permission for their own request when reviewing its interpretation.
Both participants' activity and duration boundaries are enforced before agents
receive options. Each agent receives its owner's private preferences in a separate
context. Public exchanges contain validated choices, never private notes or model
reasoning. Both humans approve the exact plan before calendar creation.

Local inference uses Ollama on the backend host. This demonstrates two isolated
personal agent contexts on one machine, not agents running on two user devices.
Google OAuth, conflict checks, and invitations are implemented; real provider
behavior must be tested with two approved Google test accounts.

## Five-minute walkthrough

1. Start Ollama, the backend with `--env-file .env`, and the frontend. For an AI
   demo use the local adapter with fallback disabled; do not present mock or
   deterministic results as AI inference.
2. Sign in with two Google test accounts in separate browser profiles. Connect
   both calendars and accept a friendship under Friends.
3. Each recipient chooses social availability. The connected-account prompt
   offers calendar-guided matching within editable personal hours, or social
   windows only. If using windows, publish overlapping future windows with an
   audience that permits the other person. Free calendar time alone is insufficient.
4. Under My preferences, give each account its own soft preference, such as
   “Prefer coffee and short catch-ups” and “Prefer a walk in the morning.” These
   are preferences, not guaranteed outcomes or hard restrictions.
5. Choose Plan with someone, select that friend and future days, and request
   “Coffee or a walk, 30 or 60 minutes, preferably in the morning.” Review the
   interpretation before sending. Do not promise a particular counteroffer:
   the model may agree immediately or fail to find agreement.
6. Under My plans, open **How the agents reached this plan**. Show the actual
   choices and source label. The eligible-option count describes options after
   backend checks, not a count of unique slots or an inferred explanation of
   the model's thinking. The exchange survives reload and is available to both
   request participants. Existing historical runs may have no option count.
7. Approve in each account. Refresh the plan in the first browser to see the
   second approval. Click **Add to Google Calendar**. Scheduling remains an
   explicit step after both approvals and rechecks conflicts and permissions.
8. Verify the invitation in the participants' calendars. If either calendar or
   inference is unavailable, the app reports failure; it must not silently use
   a mock calendar or claim an AI agreement.

## Scope to describe honestly

- Working focus: one-to-one planning with accepted friends, social consent,
  private preferences, bounded negotiation, two approvals, calendar invitation.
- Social-window browsing is audience controlled. Windows grant availability;
  they are not open events with RSVP capacity or automatic membership.
- Drop-in “Join me” posts, RSVP flows, group/community planning, per-device
  deployment, and automatic scheduling after the second approval are future work.
- The pitch's exhaustion and personal-time examples are illustrative. Do not
  claim the app detects mood, learns energy levels, or guarantees the model will
  interpret a private note as a hard boundary. Current hard constraints and
  explicit social permission are enforced by backend logic.

Suggested pitch wording: “Each personal agent evaluates permitted plans using
its owner's private preferences. Their limited exchange helps find a compromise;
the backend enforces boundaries, and both people decide whether to schedule it.”
