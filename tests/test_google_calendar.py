"""Mock Google at the SDK boundary; exercise requests, failures and replay recovery."""
import asyncio
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from googleapiclient.errors import HttpError
from backend import accounts
from backend.models import Proposal, Interval
from backend.services.google_calendar import GoogleCalendarAdapter
from backend.services.calendar_events import finalize_proposal
from backend.proposals import get_proposal_response, record_decision
from backend.hangouts import create_hangout_request
from backend.friendships import create_friend_request, respond_to_friend_request
from backend.services.calendar_adapter import MockCalendarAdapter


@pytest.fixture
def google_adapter(client,monkeypatch):
    adapter=GoogleCalendarAdapter()
    service=Mock()
    adapter._service=lambda uid:(service,object())
    adapter._persist=lambda *a:None
    monkeypatch.setattr(accounts,'account',lambda uid:{'email':uid+'@example.com'})
    return adapter,service


def proposal(request_record):
    return Proposal(id='google-plan',request_id=request_record.id,activity='coffee',slot={'start':request_record.start,'end':request_record.start.replace(minute=30)})


def test_busy_provider_errors_cannot_be_treated_as_free(google_adapter,request_record):
    adapter,service=google_adapter
    search=Interval(start=request_record.start,end=request_record.end)
    for result in [{'calendars':{}},{'calendars':{'primary':{'errors':[{'reason':'notFound'}]}}}]:
        service.freebusy.return_value.query.return_value.execute.return_value=result
        with pytest.raises(ValueError):asyncio.run(adapter.get_busy('demo-zaynah',search))
    service.freebusy.return_value.query.return_value.execute.return_value={'calendars':{'primary':{'busy':[{'start':search.start.isoformat(),'end':search.end.isoformat()}]}}}
    result=asyncio.run(adapter.get_busy('demo-zaynah',search))
    assert len(result)==1 and result[0].user_id=='demo-zaynah'
    assert service.freebusy.return_value.query.call_args.kwargs['body']['items']==[{'id':'primary'}]


def test_event_uses_slot_invites_both_and_stable_google_id(google_adapter,request_record):
    adapter,service=google_adapter
    plan=proposal(request_record)
    service.events.return_value.insert.return_value.execute.side_effect=lambda:service.events.return_value.insert.call_args.kwargs['body']
    first=asyncio.run(adapter.create_event(plan,['demo-zaynah','demo-daniella'],'stable-key'))
    sent=service.events.return_value.insert.call_args.kwargs
    assert sent['calendarId']=='primary' and sent['sendUpdates']=='all'
    assert len(sent['body']['attendees'])==2
    assert sent['body']['start']['dateTime']==plan.slot.start.isoformat()
    assert first==adapter.event_id('stable-key')
    service.events.return_value.insert.return_value.execute.side_effect=HttpError(SimpleNamespace(status=409,reason='Conflict'),b'{}')
    service.events.return_value.get.return_value.execute.return_value=sent['body']
    assert asyncio.run(adapter.create_event(plan,['demo-zaynah','demo-daniella'],'stable-key'))==first


def test_recovery_rejects_changed_event_and_handles_missing(google_adapter,request_record):
    adapter,service=google_adapter
    plan=proposal(request_record)
    service.events.return_value.get.return_value.execute.side_effect=HttpError(SimpleNamespace(status=404,reason='Not Found'),b'{}')
    assert asyncio.run(adapter.find_event(plan,['demo-zaynah','demo-daniella'],'key')) is None
    service.events.return_value.get.return_value.execute.side_effect=None
    service.events.return_value.get.return_value.execute.return_value={'id':adapter.event_id('key'),'status':'cancelled'}
    with pytest.raises(ValueError):asyncio.run(adapter.find_event(plan,['demo-zaynah','demo-daniella'],'key'))


def test_verified_provider_recovery_precedes_fresh_busy_check(client,request_record):
    # Existing approved fixture request has eligible social windows.
    create_hangout_request(request_record)
    friendship=create_friend_request(request_record.requester_id,request_record.invitee_id)
    respond_to_friend_request(friendship.id,request_record.invitee_id,'accept')
    plan=proposal(request_record)
    # Persistence is internal; route/service validation is independently tested.
    from backend.database import connect
    with connect() as connection:
        connection.execute('INSERT INTO proposals(id,request_id,data) VALUES (?,?,?)',(plan.id,plan.request_id,plan.model_dump_json()))
    for uid in [request_record.requester_id,request_record.invitee_id]:record_decision(plan.id,uid,'approve')
    class Recover(MockCalendarAdapter):
        async def find_event(self,*args):return 'verified-existing-google-event'
        async def get_busy(self,*args):pytest.fail('Recover before the existing event is treated as a conflict')
        async def create_event(self,*args):pytest.fail('Do not insert a second event')
    response,created=asyncio.run(finalize_proposal(plan.id,request_record.requester_id,'retry-key',Recover()))
    assert response.event_id=='verified-existing-google-event' and not created
    assert get_proposal_response(plan.id).proposal.status=='scheduled'
