"""Demo identity selection; this is not production authentication."""
import json
from pathlib import Path
from typing import Annotated

from fastapi import Depends, Header, HTTPException

from backend.models import BusyInterval, User
from backend.repositories import get_user
from backend.services.calendar_adapter import CalendarAdapter, MockCalendarAdapter


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
    return MockCalendarAdapter([BusyInterval.model_validate(value) for value in data['busy_intervals']])
