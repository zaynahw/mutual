# Mutual Backend API

Backend application for Mutual, featuring user management, social windows, friendship matching, and Google Calendar integration.

---

## 🚀 Quick Start

### 1. Requirements & Setup
Ensure you have Python installed and install dependencies:
```bash
pip install -r requirements.txt
```

Place your Google OAuth `credentials.json` file inside the `backend/` directory (make sure it is excluded from Git tracking).

### 2. Running the Server
Start the FastAPI server on port `8000`:
```bash
uvicorn backend.main:app --reload --port 8000
```

---

## 📅 Google Calendar Integration Guide

The Google Calendar integration on the `calendar-api` branch supports secure OAuth authentication with single-use state verification, independent multi-account token management, free/busy querying, and automatic "Mutual Hangouts" calendar event scheduling.

### 1. OAuth Endpoints & Flow

* **Initiate Login:**
  `GET /auth/google/login?user_id=<user_id>`
  * Generates a secure, single-use cryptographically random state token (`secrets.token_urlsafe(32)`) linked to the initiating `user_id` inside `OAUTH_STATE_STORE`.
  * Passes the state token to Google's consent flow to prevent session hijacking and cross-site request forgery (CSRF).

* **OAuth Callback:**
  `GET /oauth2callback?code=<code>&state=<state>`
  * Validates and immediately pops the single-use state token from `OAUTH_STATE_STORE`.
  * Exchanges the authorization code for credentials and securely attaches them to the verified `user_id` inside `USER_TOKEN_STORE`.

---

### 2. Initializing & Using the Calendar Adapter

To use the Google Calendar adapter within backend routes or scheduling services, instantiate `GoogleCalendarAdapter` by passing the application's token store:

```python
from backend.services.calendar_adapter import GoogleCalendarAdapter
from backend.main import USER_TOKEN_STORE

# Instantiate the adapter
calendar_adapter = GoogleCalendarAdapter(token_store=USER_TOKEN_STORE)
```

#### Available Methods

1. **Fetch Free/Busy Intervals:**
   ```python
   busy_intervals = await calendar_adapter.get_busy(
       user_id="user_123", 
       search=interval_obj
   )
   ```
   * **Behavior:** Queries the user's primary Google Calendar for conflicting busy blocks across the given time frame.
   * **Returns:** A list of `BusyInterval` models (`[BusyInterval(user_id=..., start=..., end=...)]`).

2. **Create Hangout Event:**
   ```python
   event_id = await calendar_adapter.create_event(
       proposal=proposal_obj, 
       participant_ids=["user_123", "user_456"], 
       idempotency_key="unique-proposal-key"
   )
   ```
   * **Behavior:** Automatically checks for or creates a dedicated secondary calendar named **"Mutual Hangouts"** on the host's account and inserts the event there so it doesn't clutter their primary calendar.

---

### 3. Data & Security Contracts

#### In-Memory Token Storage (`USER_TOKEN_STORE`)

Tokens are stored dynamically in memory using the verified `user_id` as the primary key:

```python
USER_TOKEN_STORE["user_123"] = {
    "token": "ya29.a0...",
    "refresh_token": "1//04...",
    "token_uri": "https://oauth2.googleapis.com/token",
    "client_id": "...",
    "client_secret": "...",
    "scopes": [
        "https://www.googleapis.com/auth/calendar.freebusy",
        "https://www.googleapis.com/auth/calendar.events"
    ]
}
```

#### Setup Prerequisites

* Ensure `credentials.json` is located in `backend/` and added to `.gitignore`.
* Server must run on `http://localhost:8000` to match the configured OAuth redirect URI (`http://localhost:8000/oauth2callback`).