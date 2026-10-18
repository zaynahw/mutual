"""Participant-only access to saved plans; approval actions come next."""
from fastapi import APIRouter

from backend.dependencies import ParticipantProposal
from backend.models import ProposalResponse

router = APIRouter(prefix="/proposals", tags=["proposals"])


@router.get("/{proposal_id}", response_model=ProposalResponse)
def get_plan(proposal: ParticipantProposal) -> ProposalResponse:
    # Approval persistence is not implemented yet; no decisions exist.
    return ProposalResponse(proposal=proposal, approvals=[])
