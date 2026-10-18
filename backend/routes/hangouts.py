"""Create and read person-first requests; matching is a separate operation."""
from uuid import uuid4
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException

from backend.dependencies import CurrentUser, ParticipantRequest, get_calendar_adapter, get_agent_adapter
from backend.hangouts import create_hangout_request, list_hangout_requests, list_hangout_overviews
from backend.models import CandidateOption, HangoutRequest, HangoutRequestCreate, HangoutOverview, NegotiationResponse, Proposal, ProposalCreate
from backend.repositories import get_user
from backend.proposals import list_proposals_for_request
from backend.services.calendar_adapter import CalendarAdapter
from backend.services.candidates import build_candidates
from backend.services.schedule import CalendarUnavailable
from backend.services.proposals import create_validated_proposal

from backend.services.agent_adapter import AgentAdapter
from backend.services.negotiation import AgentUnavailable, negotiate_request

router = APIRouter(prefix="/hangout-requests", tags=["hangout requests"])


@router.post("", response_model=HangoutRequest, status_code=201)
def create_request(body: HangoutRequestCreate, current_user: CurrentUser,
                   idempotency_key: Annotated[str | None, Header(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")] = None) -> HangoutRequest:
    if body.invitee_id == current_user.id:
        raise HTTPException(status_code=422, detail="Participants must be different")
    if get_user(body.invitee_id) is None:
        raise HTTPException(status_code=404, detail="Invitee not found")
    request = HangoutRequest(
        **body.model_dump(), id=f"request-{uuid4()}", requester_id=current_user.id,
    )
    try:
        return create_hangout_request(request, idempotency_key)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("", response_model=list[HangoutRequest])
def get_my_requests(current_user: CurrentUser) -> list[HangoutRequest]:
    return list_hangout_requests(current_user.id)


@router.get("/overview", response_model=list[HangoutOverview])
def get_my_overviews(current_user: CurrentUser) -> list[HangoutOverview]:
    return list_hangout_overviews(current_user.id)


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
    current_user: CurrentUser,
    body: ProposalCreate,
    calendar: Annotated[CalendarAdapter, Depends(get_calendar_adapter)],
    idempotency_key: Annotated[str | None, Header(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")] = None,
) -> Proposal:
    try:
        return await create_validated_proposal(request, body, calendar, current_user.id, idempotency_key)
    except LookupError as error:
        raise HTTPException(status_code=404, detail="Participant not found") from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except CalendarUnavailable as error:
        raise HTTPException(status_code=502, detail="Calendar availability is temporarily unavailable") from error


@router.get("/{request_id}/proposals", response_model=list[Proposal])
def get_request_proposals(request: ParticipantRequest) -> list[Proposal]:
    return list_proposals_for_request(request.id)


@router.post("/{request_id}/negotiate", response_model=NegotiationResponse)
async def negotiate(
    request: ParticipantRequest,
    current_user: CurrentUser,
    idempotency_key: Annotated[str, Header(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")],
    calendar: Annotated[CalendarAdapter, Depends(get_calendar_adapter)],
    agent: Annotated[AgentAdapter, Depends(get_agent_adapter)],
    variation: Literal["any", "different_time"] = "any",
) -> NegotiationResponse:
    try:
        return await negotiate_request(request, current_user.id, idempotency_key, calendar, agent, variation)
    except LookupError as error:
        raise HTTPException(status_code=404, detail="Hangout request not found") from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except CalendarUnavailable as error:
        raise HTTPException(status_code=502, detail="Calendar availability is temporarily unavailable") from error
    except AgentUnavailable as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@router.get("/{request_id}/negotiation", response_model=NegotiationResponse | None)
def get_negotiation(request: ParticipantRequest, current_user: CurrentUser) -> NegotiationResponse | None:
    from backend.negotiations import latest_negotiation
    return latest_negotiation(request.id, current_user.id)
