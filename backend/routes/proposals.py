"""Participant-only access to saved plans; record immutable approval decisions."""
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response

from backend.dependencies import CurrentUser, ParticipantProposal, get_calendar_adapter
from backend.models import ApprovalCreate, CalendarEventResponse, ProposalResponse
from backend.proposals import get_proposal_response, record_decision, replan_proposal

from backend.services.calendar_adapter import CalendarAdapter
from backend.services.calendar_events import finalize_proposal
from backend.services.schedule import CalendarUnavailable

router = APIRouter(prefix="/proposals", tags=["proposals"])


@router.get("/{proposal_id}", response_model=ProposalResponse)
def get_plan(proposal: ParticipantProposal) -> ProposalResponse:
    return get_proposal_response(proposal.id)


@router.post("/{proposal_id}/approvals", response_model=ProposalResponse)
def decide(proposal: ParticipantProposal, body: ApprovalCreate, current_user: CurrentUser) -> ProposalResponse:
    try:
        return record_decision(proposal.id, current_user.id, body.decision)
    except LookupError as error:
        raise HTTPException(status_code=404, detail="Proposal not found") from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/{proposal_id}/calendar-event", response_model=CalendarEventResponse, status_code=201,
             responses={200: {"model": CalendarEventResponse}})
async def schedule(
    proposal: ParticipantProposal,
    current_user: CurrentUser,
    response: Response,
    idempotency_key: Annotated[str, Header(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")],
    calendar: Annotated[CalendarAdapter, Depends(get_calendar_adapter)],
) -> CalendarEventResponse:
    try:
        result, created = await finalize_proposal(proposal.id, current_user.id, idempotency_key, calendar)
    except LookupError as error:
        raise HTTPException(status_code=404, detail="Proposal not found") from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except CalendarUnavailable as error:
        raise HTTPException(status_code=502, detail="Calendar service is temporarily unavailable") from error
    response.status_code = 201 if created else 200
    return result


@router.post("/{proposal_id}/replan", response_model=ProposalResponse)
def replan(proposal: ParticipantProposal, current_user: CurrentUser) -> ProposalResponse:
    try:
        return replan_proposal(proposal.id, current_user.id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail="Proposal not found") from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
