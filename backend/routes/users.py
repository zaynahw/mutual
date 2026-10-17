"""Read-only public directory and private owner profile."""
from typing import Annotated

from fastapi import APIRouter, Depends

from backend.dependencies import get_current_user
from backend.models import PublicUser, User
from backend.repositories import list_users

router = APIRouter(prefix="/users", tags=["users"])
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get("", response_model=list[PublicUser])
def get_users(current_user: CurrentUser) -> list[PublicUser]:
    return [
        PublicUser(id=user.id, display_name=user.display_name,
                   is_demo=user.is_demo, community=user.community)
        for user in list_users()
    ]


@router.get("/me", response_model=User)
def get_me(current_user: CurrentUser) -> User:
    return current_user
