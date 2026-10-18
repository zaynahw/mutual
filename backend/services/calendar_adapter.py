"""Calendar boundary: free/busy only; event creation requires backend approval checks."""
from typing import Protocol
from fastapi import HTTPException
from backend.models import BusyInterval, Interval, Proposal
from datetime import datetime, timezone
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

class CalendarAdapter(Protocol):
    async def get_busy(self, user_id: str, search: Interval) -> list[BusyInterval]: ...
    async def create_event(self, proposal: Proposal, participant_ids: list[str], idempotency_key: str) -> str: ...

class MockCalendarAdapter:
    def __init__(self, busy: list[BusyInterval] | None = None):
        self.busy = busy or []
        self.events: dict[str, str] = {}

    async def get_busy(self, user_id: str, search: Interval) -> list[BusyInterval]:
        return [b for b in self.busy if b.user_id == user_id and b.start < search.end and b.end > search.start]

    async def create_event(self, proposal: Proposal, participant_ids: list[str], idempotency_key: str) -> str:
        # Caller must enforce permissions and both approvals, even for mocks.
        return self.events.setdefault(idempotency_key, f"demo-event-{proposal.id}")

class GoogleCalendarAdapter:
    def __init__(self, token_store: dict):
        self.token_store = token_store

    async def get_busy(self, user_id: str, search: Interval) -> list[BusyInterval]:
        # Support both dictionary lookups and object-style token store wrappers if used by teammates
        if hasattr(self.token_store, "get_token"):
            credentials_data = self.token_store.get_token(user_id)
        else:
            credentials_data = self.token_store.get(user_id)

        if not credentials_data:
            raise HTTPException(status_code=404, detail=f"No calendar linked for user {user_id}")

        creds = Credentials(**credentials_data)
        service = build('calendar', 'v3', credentials=creds)


        body = {
            "timeMin": search.start.isoformat(),
            "timeMax": search.end.isoformat(),
            "items": [{"id": "primary"}]
        }

        events_result = service.freebusy().query(body=body).execute()
        calendar_data = events_result.get('calendars', {}).get('primary', {})
        busy_slots = calendar_data.get('busy', [])

        result = []
        for slot in busy_slots:
            result.append(BusyInterval(
                user_id=user_id,
                start=datetime.fromisoformat(slot['start'].replace('Z', '+00:00')),
                end=datetime.fromisoformat(slot['end'].replace('Z', '+00:00'))
            ))
        return result

    async def create_event(self, proposal: Proposal, participant_ids: list[str], idempotency_key: str) -> str:
        if not participant_ids:
            raise ValueError("Cannot create calendar event without participants.")

        host_id = participant_ids[0]
        token_data = self.token_storage.get_token(host_id)
        if not token_data:
            raise ValueError(f"No valid credentials found for host {host_id}")

        creds = Credentials(**token_data)
        service = build('calendar', 'v3', credentials=creds)

        # 1. Get or create the dedicated "Mutual Hangouts" calendar ID
        app_calendar_id = await self._get_or_create_app_calendar(service)

        event_body = {
            'summary': f"Mutual Hangout: {proposal.activity}",
            'description': 'Scheduled automatically via Mutual agents 🤖',
            'start': {'dateTime': proposal.start.isoformat()},
            'end': {'dateTime': proposal.end.isoformat()},
        }

        # 2. Insert the event into the dedicated app calendar instead of 'primary'
        created_event = service.events().insert(
            calendarId=app_calendar_id, 
            body=event_body
        ).execute()

        return created_event.get('id', f"google-event-{proposal.id}")

    async def _get_or_create_app_calendar(self, service) -> str:
        """Finds the 'Mutual Hangouts' calendar or creates one if it doesn't exist."""
        calendar_list = service.calendarList().list().execute()
        for entry in calendar_list.get('items', []):
            if entry.get('summary') == 'Mutual Hangouts':
                return entry['id']
        
        # If it doesn't exist yet, create a new secondary calendar
        new_calendar = {
            'summary': 'Mutual Hangouts',
            'description': 'Hangouts scheduled automatically through the Mutual app 🤖'
        }
        created = service.calendars().body(new_calendar).execute() if hasattr(service, 'calendars') else service.calendars().insert(body=new_calendar).execute()
        return created['id']