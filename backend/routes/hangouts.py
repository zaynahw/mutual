"""Create and read person-first requests; matching is a separate operation."""
from uuid import uuid4
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from backend.dependencies import CurrentUser, ParticipantRequest, get_calendar_adapter
from backend.hangouts import create_hangout_request, list_hangout_requests
from backend.models import CandidateOption, HangoutRequest, HangoutRequestCreate, Proposal, ProposalCreate
from backend.repositories import get_user
from backend.services.calendar_adapter import CalendarAdapter
from backend.services.candidates import build_candidates
from backend.services.schedule import CalendarUnavailable
from backend.services.proposals import create_validated_proposal

router = APIRouter(prefix="/hangout-requests", tags=["hangout requests"])


@router.post("", response_model=HangoutRequest, status_code=201)
def create_request(body: HangoutRequestCreate, current_user: CurrentUser) -> HangoutRequest:
    if body.invitee_id == current_user.id:
        raise HTTPException(status_code=422, detail="Participants must be different")
    if get_user(body.invitee_id) is None:
        raise HTTPException(status_code=404, detail="Invitee not found")
    request = HangoutRequest(
        **body.model_dump(), id=f"request-{uuid4()}", requester_id=current_user.id,
    )
    create_hangout_request(request)
    return request


@router.get("", response_model=list[HangoutRequest])
def get_my_requests(current_user: CurrentUser) -> list[HangoutRequest]:
    return list_hangout_requests(current_user.id)


@router.get("/{request_id}", response_model=HangoutRequest)
def get_request(request: ParticipantRequest) -> HangoutRequest:
    return request


@router.post("/{request_id}/candidates", response_model=list[CandidateOption])
async def get_candidates(
    request: ParticipantRequest,
    calendar: Annotated[CalendarAdapter, Depends(get_calendar_adapter)],
) -> list[CandidateOption]:
    try:
        return await build_candidates(request, calendar)
    except LookupError as error:
        raise HTTPException(status_code=404, detail="Participant not found") from error
    except CalendarUnavailable as error:
        raise HTTPException(status_code=502, detail="Calendar availability is temporarily unavailable") from error


@router.post("/{request_id}/proposals", response_model=Proposal, status_code=201)
async def propose(
    request: ParticipantRequest,
    body: ProposalCreate,
    calendar: Annotated[CalendarAdapter, Depends(get_calendar_adapter)],
) -> Proposal:
    try:
        return await create_validated_proposal(request, body, calendar)
    except LookupError as error:
        raise HTTPException(status_code=404, detail="Participant not found") from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except CalendarUnavailable as error:
        raise HTTPException(status_code=502, detail="Calendar availability is temporarily unavailable") from error
