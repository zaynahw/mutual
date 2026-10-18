"""Interpret privately, confirm explicitly, then compile selected local dates."""
import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

from backend.friendships import are_friends
from backend.hangouts import create_hangout_request, get_hangout_request
from backend.intents import get_intent, mark_sent, save_intent
from backend.models import HangoutIntentCreate, HangoutIntentDraft, HangoutRequest, Interval, User
from backend.repositories import get_user
from backend.services.agent_adapter import AgentAdapter
from backend.services.intent_dates import local_instant
from backend.services.negotiation import AgentUnavailable


def validate_days(body: HangoutIntentCreate, timezone_name: str) -> None:
    today = datetime.now(ZoneInfo(timezone_name)).date()
    if any(day < today or day > today + timedelta(days=14) for day in body.days):
        raise ValueError('Choose dates from today through the next 14 days')


async def interpret_intent(body: HangoutIntentCreate, owner: User, agent: AgentAdapter) -> HangoutIntentDraft:
    validate_days(body,owner.timezone)
    if body.invitee_id == owner.id or get_user(body.invitee_id) is None or not are_friends(owner.id,body.invitee_id):
        raise ValueError('Choose a currently accepted friend for this request')
    try:
        result = await asyncio.wait_for(agent.interpret(body,owner.timezone,datetime.now(ZoneInfo(owner.timezone)).date()),timeout=60)
    except Exception as error:
        raise AgentUnavailable() from error
    draft = HangoutIntentDraft(id=f'intent-{uuid4()}',owner_id=owner.id,input=body,timezone=owner.timezone,result=result)
    save_intent(draft)
    return draft


def send_intent(intent_id: str, owner: User) -> HangoutRequest:
    draft = get_intent(intent_id,owner.id)
    if draft is None: raise LookupError('Request draft not found')
    if draft.request_id:
        existing = get_hangout_request(draft.request_id)
        if existing is not None: return existing
    validate_days(draft.input,draft.timezone)
    if owner.timezone != draft.timezone:
        raise ValueError('Your timezone changed. Interpret the request again before sending')
    if not are_friends(owner.id,draft.input.invitee_id):
        raise ValueError('This person is no longer an accepted friend')
    interpretation = draft.result.interpretation
    if interpretation.clarification:
        raise ValueError('Please answer the clarification by editing the message and interpreting it again')
    windows = []
    for day in draft.input.days:
        start = local_instant(day,interpretation.earliest or '00:00',draft.timezone)
        end = local_instant(day,interpretation.latest,draft.timezone) if interpretation.latest else local_instant(day+timedelta(days=1),'00:00',draft.timezone)
        windows.append(Interval(start=start,end=end))
    now = datetime.now(timezone.utc)
    if all(window.end <= now for window in windows):
        raise ValueError('Those times have already passed. Choose another day or relax the required time limit')
    request = HangoutRequest(
        id=f'request-{draft.id}',requester_id=owner.id,invitee_id=draft.input.invitee_id,
        start=windows[0].start,end=windows[-1].end,search_windows=windows,
        allowed_activities=interpretation.activities,allowed_durations=interpretation.allowed_durations,
        origin='intent',
    )
    request = create_hangout_request(request,idempotency_key=draft.id)
    mark_sent(draft.id,owner.id,request.id)
    return request
