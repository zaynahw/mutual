"""Mutual API. Seed the local database before using user routes."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.routes.users import router as users_router
from backend.routes.social_windows import router as social_windows_router

app = FastAPI(title="Mutual", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["X-Demo-User-Id", "Content-Type"])

app.include_router(users_router)
app.include_router(social_windows_router)

class HealthResponse(BaseModel):
    status: str = "ok"

@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()
