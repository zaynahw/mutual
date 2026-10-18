"""Google calendar lane integration, using primary calendars and stable event IDs.

Primary-calendar writes keep events visible to subsequent free/busy checks without
requesting calendar-list or calendar-creation permissions. Both participants are
invited to the same event; backend approval checks still own consent.
"""
import asyncio
import hashlib
import json
from datetime import datetime
import httplib2
from google_auth_httplib2 import AuthorizedHttp
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from backend import accounts
from backend.database import connect
from backend.models import BusyInterval, Interval, Proposal


class GoogleCalendarAdapter:
    def __init__(self,token_store=None):
        self.token_store=token_store

    def _data(self,user_id: str) -> dict:
        if self.token_store is None:return accounts.credentials(user_id)
        value=self.token_store.get_token(user_id) if hasattr(self.token_store,'get_token') else self.token_store.get(user_id)
        if not value:raise ValueError('Connect Google Calendar before checking availability')
        return value

    def _service(self,user_id: str):
        creds=Credentials.from_authorized_user_info(self._data(user_id))
        http=AuthorizedHttp(creds,http=httplib2.Http(timeout=30))
        return build('calendar','v3',http=http,cache_discovery=False),creds

    def _persist(self,user_id: str,creds) -> None:
        if self.token_store is None:accounts.save_credentials(user_id,json.loads(creds.to_json()))

    async def get_busy(self,user_id: str,search: Interval) -> list[BusyInterval]:
        return await asyncio.to_thread(self._busy,user_id,search)

    def _busy(self,user_id: str,search: Interval) -> list[BusyInterval]:
        service,creds=self._service(user_id)
        result=service.freebusy().query(body={'timeMin':search.start.isoformat(),'timeMax':search.end.isoformat(),
                                             'items':[{'id':'primary'}]}).execute()
        calendar=result.get('calendars',{}).get('primary')
        if calendar is None or calendar.get('errors') or 'busy' not in calendar:
            raise ValueError('Calendar availability could not be verified')
        intervals=[BusyInterval(user_id=user_id,start=slot['start'],end=slot['end']) for slot in calendar['busy']]
        # Include confirmed Mutual bookings for both participants even before
        # the invitee accepts Google's separate email invitation.
        with connect() as connection:
            rows=connection.execute("""SELECT p.data FROM calendar_events e
                JOIN proposals p ON p.id=e.proposal_id
                JOIN hangout_requests r ON r.id=p.request_id
                WHERE e.status='completed' AND e.event_id NOT LIKE 'demo-event-%'
                AND (r.requester_id=? OR r.invitee_id=?)""",(user_id,user_id)).fetchall()
        for row in rows:
            plan=Proposal.model_validate_json(row['data'])
            if plan.slot.start<search.end and plan.slot.end>search.start:
                intervals.append(BusyInterval(user_id=user_id,**plan.slot.model_dump()))
        self._persist(user_id,creds)
        return intervals

    @staticmethod
    def event_id(key: str) -> str:
        # Google IDs allow lowercase base32hex; SHA256 hex is a valid subset.
        return 'mutual'+hashlib.sha256(key.encode()).hexdigest()

    async def create_event(self,proposal: Proposal,participant_ids: list[str],idempotency_key: str) -> str:
        return await asyncio.to_thread(self._create,proposal,participant_ids,idempotency_key)

    def _validate(self,event: dict,proposal: Proposal,participants: list[str],key: str) -> str:
        expected=self.event_id(key)
        if event.get('id')!=expected or event.get('status')=='cancelled':raise ValueError('Provider event does not match this plan')
        for field,value in [('start',proposal.slot.start),('end',proposal.slot.end)]:
            received=event.get(field,{}).get('dateTime')
            if not received or datetime.fromisoformat(received.replace('Z','+00:00'))!=value:
                raise ValueError('Provider event time does not match this plan')
        if event.get('extendedProperties',{}).get('private',{}).get('mutual_proposal_id')!=proposal.id:
            raise ValueError('Provider event does not belong to this proposal')
        emails={accounts.account(uid)['email'].lower() for uid in participants}
        if not emails <= {item.get('email','').lower() for item in event.get('attendees',[])}:
            raise ValueError('Provider event participants do not match this plan')
        return expected

    def _create(self,proposal: Proposal,participants: list[str],key: str) -> str:
        if len(set(participants))!=2:raise ValueError('Two distinct participants are required')
        host=participants[0]
        people=[accounts.account(uid) for uid in participants]
        if any(not person for person in people):raise ValueError('Both participants need Google accounts')
        service,creds=self._service(host)
        body={'id':self.event_id(key),'summary':f'Mutual Hangout: {proposal.activity}',
              'description':'Both participants approved this Mutual hangout.',
              'start':{'dateTime':proposal.slot.start.isoformat()},'end':{'dateTime':proposal.slot.end.isoformat()},
              'attendees':[{'email':person['email']} for person in people],
              'extendedProperties':{'private':{'mutual_proposal_id':proposal.id}}}
        if proposal.location:body['location']=proposal.location
        try:
            result=service.events().insert(calendarId='primary',body=body,sendUpdates='all').execute()
        except HttpError as error:
            if error.resp.status!=409:raise
            result=service.events().get(calendarId='primary',eventId=body['id']).execute()
        event_id=self._validate(result,proposal,participants,key)
        self._persist(host,creds)
        return event_id

    async def find_event(self,proposal: Proposal,participant_ids: list[str],key: str) -> str | None:
        # Recover a successful write whose HTTP response was lost, before its own
        # busy interval would otherwise make fresh availability reject the retry.
        def find():
            service,creds=self._service(participant_ids[0])
            try:event=service.events().get(calendarId='primary',eventId=self.event_id(key)).execute()
            except HttpError as error:
                if error.resp.status==404:return None
                raise
            result=self._validate(event,proposal,participant_ids,key)
            self._persist(participant_ids[0],creds)
            return result
        return await asyncio.to_thread(find)
