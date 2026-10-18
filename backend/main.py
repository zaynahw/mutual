"""Mutual API. Seed the local database before using user routes."""
from contextlib import asynccontextmanager
from backend.database import initialize_database
from backend import settings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.routes.availability_board import router as availability_board_router
from backend.routes.auth import router as auth_router
from backend.routes.intents import router as intents_router
from backend.routes.users import router as users_router
from backend.routes.hangouts import router as hangouts_router
from backend.routes.friendships import router as friendships_router
from backend.routes.social_windows import router as social_windows_router
from backend.routes.proposals import router as proposals_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database()
    yield

app = FastAPI(title="Mutual", version="0.1.0", lifespan=lifespan)
app.include_router(auth_router)
app.add_middleware(CORSMiddleware, allow_origins=[settings.frontend_url()], allow_credentials=True, allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"], allow_headers=["X-Demo-User-Id", "Content-Type", "Idempotency-Key"])

app.include_router(availability_board_router)
app.include_router(intents_router)
app.include_router(users_router)
app.include_router(hangouts_router)
app.include_router(friendships_router)
app.include_router(social_windows_router)
app.include_router(proposals_router)

class HealthResponse(BaseModel):
    status: str = "ok"

@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()
