"""Create and read person-first requests; matching is a separate operation."""
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from backend.dependencies import CurrentUser, ParticipantRequest
from backend.hangouts import create_hangout_request, list_hangout_requests
from backend.models import HangoutRequest, HangoutRequestCreate
from backend.repositories import get_user

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
