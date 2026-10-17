"""Read-only public directory and private owner profile."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.dependencies import CurrentUser, get_calendar_adapter
from backend.models import Interval, PublicUser, ScheduleResponse, User
from backend.repositories import get_user, list_users
from backend.services.calendar_adapter import CalendarAdapter
from backend.services.schedule import CalendarUnavailable, build_schedule

router = APIRouter(prefix="/users", tags=["users"])


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


@router.get("/{user_id}/schedule", response_model=ScheduleResponse)
async def get_schedule(
    user_id: str,
    current_user: CurrentUser,
    search: Annotated[Interval, Query()],
    calendar: Annotated[CalendarAdapter, Depends(get_calendar_adapter)],
) -> ScheduleResponse:
    owner = get_user(user_id)
    if owner is None:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        return await build_schedule(owner=owner, viewer=current_user, search=search, calendar=calendar)
    except CalendarUnavailable as error:
        raise HTTPException(status_code=502, detail="Calendar availability is temporarily unavailable") from error
