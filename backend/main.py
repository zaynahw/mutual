"""Mutual API. Seed the local database before using user routes."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google_auth_oauthlib.flow import Flow

from backend.routes.users import router as users_router
from backend.routes.friendships import router as friendships_router
from backend.routes.social_windows import router as social_windows_router

app = FastAPI(title="Mutual", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["X-Demo-User-Id", "Content-Type"])

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

class SimpleTokenStore:
    def get_token(self, user_id: str):
        return USER_TOKEN_STORE.get(user_id)

@app.get("/auth/google/login")
def login_google(user_id: str):
    """Initiates the Google OAuth flow for a specific user ID."""
    if not os.path.exists(CLIENT_SECRETS_FILE):
        raise HTTPException(status_code=500, detail="credentials.json not found in backend folder.")
    
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        state=user_id  # Pass user_id through state to capture it on return
    )
    return {"authorization_url": authorization_url}

@app.get("/oauth2callback")
def oauth2callback(request: Request, code: str, state: str):
    """Handles Google's redirect, extracts tokens, and stores them under the user_id."""
    user_id = state  
    
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    flow.fetch_token(code=code)
    creds = flow.credentials
    
    USER_TOKEN_STORE[user_id] = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes
    }
    
    return {"status": "success", "message": f"Google Calendar successfully linked for user: {user_id}!"}