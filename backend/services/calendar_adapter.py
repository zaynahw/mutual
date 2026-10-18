"""Calendar boundary: free/busy only; event creation requires backend approval checks."""
from typing import Protocol
from backend.models import BusyInterval, Interval, Proposal

class CalendarAdapter(Protocol):
    """create_event must deduplicate the stable key at the calendar provider.

    Retries can arrive after a timeout, process restart, or expired worker lease.
    An in-memory key cache alone is insufficient for the real integration.
    """
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

# Kept here as a compatibility export for the calendar lane.
from backend.services.google_calendar import GoogleCalendarAdapter
