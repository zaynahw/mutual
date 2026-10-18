"""Demo identity selection; this is not production authentication."""
import json
from pathlib import Path
from typing import Annotated

from fastapi import Depends, Header, HTTPException

from backend.models import BusyInterval, HangoutRequest, Proposal, User
from backend.proposals import get_proposal
from backend.repositories import get_user
from backend.hangouts import get_hangout_request
from backend.services.calendar_adapter import CalendarAdapter
from backend.services.demo_calendar import DemoCalendarAdapter
from backend.services.agent_adapter import AgentAdapter, build_agent_adapter


def get_current_user(
    demo_user_id: Annotated[str | None, Header(alias="X-Demo-User-Id")] = None,
) -> User:
    if demo_user_id is None:
        raise HTTPException(status_code=401, detail="Select a demo user")
    user = get_user(demo_user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Unknown demo user")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_calendar_adapter() -> CalendarAdapter:
    """Demo calendar source; replace/override this dependency for real integration.

    Busy fixtures are simulated and stay outside SQLite. No OAuth calls occur.
    """
    fixture = Path(__file__).resolve().parents[1] / 'contracts' / 'examples.json'
    data = json.loads(fixture.read_text())
    return DemoCalendarAdapter([BusyInterval.model_validate(value) for value in data['busy_intervals']])


def get_participant_request(request_id: str, current_user: CurrentUser) -> HangoutRequest:
    """Shared access check for request retrieval and future matching endpoints."""
    request = get_hangout_request(request_id)
    if request is None or current_user.id not in (request.requester_id, request.invitee_id):
        raise HTTPException(status_code=404, detail="Hangout request not found")
    return request


ParticipantRequest = Annotated[HangoutRequest, Depends(get_participant_request)]


def get_participant_proposal(proposal_id: str, current_user: CurrentUser) -> Proposal:
    """Conceal missing proposals and plans belonging to other participants."""
    proposal = get_proposal(proposal_id)
    request = get_hangout_request(proposal.request_id) if proposal else None
    if request is None or current_user.id not in (request.requester_id, request.invitee_id):
        raise HTTPException(status_code=404, detail="Proposal not found")
    return proposal


ParticipantProposal = Annotated[Proposal, Depends(get_participant_proposal)]


def get_agent_adapter() -> AgentAdapter:
    return build_agent_adapter()
