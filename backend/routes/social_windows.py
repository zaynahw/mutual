"""Owner-only social availability. Viewer filtering is a separate future service."""
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Response

from backend.dependencies import CurrentUser
from backend.models import SocialWindow, SocialWindowCreate
from backend.repositories import (
    create_social_window, delete_social_window, list_social_windows, update_social_window,
)

router = APIRouter(prefix="/users/me/social-windows", tags=["social windows"])


@router.get("", response_model=list[SocialWindow])
def get_my_windows(current_user: CurrentUser) -> list[SocialWindow]:
    return list_social_windows(current_user.id)


@router.post("", response_model=SocialWindow, status_code=201)
def add_my_window(body: SocialWindowCreate, current_user: CurrentUser) -> SocialWindow:
    if body.visibility.audience == "selected_friends":
        raise HTTPException(status_code=409, detail="Selected-friends sharing needs friendship setup")
    window = SocialWindow(**body.model_dump(), id=f"window-{uuid4()}", user_id=current_user.id)
    create_social_window(window)
    return window


@router.put("/{window_id}", response_model=SocialWindow)
def edit_my_window(window_id: str, body: SocialWindowCreate, current_user: CurrentUser) -> SocialWindow:
    if body.visibility.audience == "selected_friends":
        raise HTTPException(status_code=409, detail="Selected-friends sharing needs friendship setup")
    window = SocialWindow(**body.model_dump(), id=window_id, user_id=current_user.id)
    if not update_social_window(window):
        raise HTTPException(status_code=404, detail="Social window not found")
    return window


@router.delete("/{window_id}", status_code=204)
def remove_my_window(window_id: str, current_user: CurrentUser) -> Response:
    if not delete_social_window(window_id, current_user.id):
        raise HTTPException(status_code=404, detail="Social window not found")
    return Response(status_code=204)
