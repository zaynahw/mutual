"""Natural-language request drafts are private until explicitly confirmed."""
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from backend.dependencies import CurrentUser, get_agent_adapter
from backend.intents import get_intent
from backend.models import HangoutIntentCreate, HangoutIntentDraft, HangoutRequest
from backend.services.agent_adapter import AgentAdapter
from backend.services.intents import interpret_intent, send_intent
from backend.services.negotiation import AgentUnavailable

router = APIRouter(prefix='/hangout-intents',tags=['hangout intents'])


@router.post('/interpret',response_model=HangoutIntentDraft)
async def interpret(body: HangoutIntentCreate,current_user: CurrentUser,agent: Annotated[AgentAdapter,Depends(get_agent_adapter)]) -> HangoutIntentDraft:
    try:
        return await interpret_intent(body,current_user,agent)
    except ValueError as error:
        raise HTTPException(status_code=422,detail=str(error)) from error
    except AgentUnavailable as error:
        raise HTTPException(status_code=502,detail='Could not interpret the message; try again or use the manual form') from error


@router.get('/{intent_id}',response_model=HangoutIntentDraft)
def read_draft(intent_id: str,current_user: CurrentUser) -> HangoutIntentDraft:
    draft = get_intent(intent_id,current_user.id)
    if draft is None: raise HTTPException(status_code=404,detail='Request draft not found')
    return draft


@router.post('/{intent_id}/send',response_model=HangoutRequest)
def send(intent_id: str,current_user: CurrentUser) -> HangoutRequest:
    try:
        return send_intent(intent_id,current_user)
    except LookupError as error:
        raise HTTPException(status_code=404,detail='Request draft not found') from error
    except ValueError as error:
        raise HTTPException(status_code=409,detail=str(error)) from error
