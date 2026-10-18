"""Fixture calendar plus persisted simulated bookings; never used by Google."""
from backend.database import connect
from backend.models import BusyInterval, Interval, Proposal
from backend.services.calendar_adapter import MockCalendarAdapter


class DemoCalendarAdapter(MockCalendarAdapter):
    async def get_busy(self, user_id: str, search: Interval) -> list[BusyInterval]:
        busy = await super().get_busy(user_id, search)
        with connect() as connection:
            rows = connection.execute('''
                SELECT p.data FROM calendar_events e
                JOIN proposals p ON p.id = e.proposal_id
                JOIN hangout_requests r ON r.id = p.request_id
                WHERE e.status = 'completed' AND e.event_id LIKE 'demo-event-%'
                  AND (r.requester_id = ? OR r.invitee_id = ?)
            ''', (user_id, user_id)).fetchall()
        for row in rows:
            proposal = Proposal.model_validate_json(row['data'])
            if proposal.slot.start < search.end and proposal.slot.end > search.start:
                busy.append(BusyInterval(user_id=user_id, **proposal.slot.model_dump()))
        return busy
