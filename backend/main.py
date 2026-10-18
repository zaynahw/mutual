"""Mutual API. Seed the local database before using user routes."""
import os
import secrets
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google_auth_oauthlib.flow import Flow

from backend.routes.users import router as users_router
from backend.routes.friendships import router as friendships_router
from backend.routes.social_windows import router as social_windows_router

app = FastAPI(title="Mutual", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["*"])

app.include_router(users_router)
app.include_router(friendships_router)
app.include_router(social_windows_router)

class HealthResponse(BaseModel):
    status: str = "ok"

@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()

# ==========================================
# CALENDAR BACKEND OAUTH ROUTES
# ==========================================

CLIENT_SECRETS_FILE = os.path.join(os.path.dirname(__file__), "credentials.json")
SCOPES = [
    "https://www.googleapis.com/auth/calendar.freebusy",
    "https://www.googleapis.com/auth/calendar.events"
]
REDIRECT_URI = "http://localhost:8000/oauth2callback"

# In-memory storage for hackathon demo tokens: user_id -> token dictionary
USER_TOKEN_STORE = {}

# Temporary in-memory store for active OAuth states: state_token -> user_id
OAUTH_STATE_STORE = {}

class SimpleTokenStore:
    def get_token(self, user_id: str):
        return USER_TOKEN_STORE.get(user_id)


@app.get("/auth/google/login")
def google_login(user_id: str, request: Request):
    # 1. Generate a secure, unpredictable random token
    state_token = secrets.token_urlsafe(32)
    
    # 2. Store it tied to this specific user_id
    OAUTH_STATE_STORE[state_token] = user_id
    
    # 3. Pass the state token into the Google OAuth flow
    flow = Flow.from_client_secrets_file(CLIENT_SECRETS_FILE, scopes=SCOPES)
    flow.redirect_uri = REDIRECT_URI
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        state=state_token  # Send our secure token to Google
    )
    
    return {"authorization_url": authorization_url}

@app.get("/oauth2callback")
def oauth2callback(request: Request, code: str, state: str):
    # 1. Verify that the state token exists and is valid (Single-use protection)
    stored_user_id = OAUTH_STATE_STORE.pop(state, None)
    if not stored_user_id:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state token.")
    
    # 2. Exchange authorization code for tokens
    flow = Flow.from_client_secrets_file(CLIENT_SECRETS_FILE, scopes=SCOPES)
    flow.redirect_uri = REDIRECT_URI
    flow.fetch_token(code=code)
    
    credentials = flow.credentials
    
    # 3. Save credentials securely tied to the verified user ID
    USER_TOKEN_STORE[stored_user_id] = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes
    }
    
    return {"status": "success", "message": f"Google Calendar successfully linked for user: {stored_user_id}"}