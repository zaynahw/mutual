"""Browse explicitly published social availability, never provider calendars."""
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Depends, Header

from backend.dependencies import CurrentUser, get_calendar_adapter
from backend.models import AvailabilityCard, HangoutOverview, Interval, ProposalCreate, PublicUser, SharedSocialWindow
from backend.repositories import list_social_windows, list_users
from backend.services.permissions import can_access
from backend.services.schedule import clip_interval
from backend.services.calendar_adapter import CalendarAdapter

router = APIRouter(prefix='/availability-board', tags=['community'])


@router.get('', response_model=list[AvailabilityCard])
def availability_board(current_user: CurrentUser, search: Annotated[Interval, Query()]) -> list[AvailabilityCard]:
    if search.end.astimezone(timezone.utc) - search.start.astimezone(timezone.utc) > timedelta(days=14):
        raise HTTPException(status_code=422, detail='Choose a range of at most 14 days')
    now = datetime.now(timezone.utc)
    cards = []
    for owner in list_users():
        if owner.is_demo != current_user.is_demo:
            continue
        for window in list_social_windows(owner.id):
            if window.sharing_mode != 'visible' or window.visibility.audience == 'private':
                continue
            if not can_access(owner, current_user, window.visibility) or window.end <= now:
                continue
            clipped = clip_interval(window, search)
            if clipped is not None:
                cards.append(AvailabilityCard(
                    owner=PublicUser(id=owner.id, display_name=owner.display_name,
                                     is_demo=owner.is_demo, community=owner.community),
                    window=SharedSocialWindow(id=window.id, title=window.title, **clipped.model_dump(),
                                              allowed_activities=window.allowed_activities),
                    audience=window.visibility.audience,
                ))
    return sorted(cards, key=lambda card: (card.window.start, card.owner.id, card.window.id))


@router.post('/{owner_id}/{window_id}/join', response_model=HangoutOverview, status_code=201)
async def join_window(owner_id: str, window_id: str, body: ProposalCreate, current_user: CurrentUser,
                      idempotency_key: Annotated[str, Header(min_length=1,max_length=128,pattern=r"^[A-Za-z0-9_-]+$")],
                      calendar: Annotated[CalendarAdapter, Depends(get_calendar_adapter)]):
    from backend.services.join_window import request_join
    from backend.services.schedule import CalendarUnavailable
    try:
        return await request_join(owner_id,window_id,current_user,body,idempotency_key,calendar)
    except LookupError as error:
        raise HTTPException(status_code=404,detail='Shared window not found') from error
    except ValueError as error:
        raise HTTPException(status_code=409,detail=str(error)) from error
    except CalendarUnavailable as error:
        raise HTTPException(status_code=502,detail='Calendar availability is temporarily unavailable') from error
