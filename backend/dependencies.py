"""Demo identity selection; this is not production authentication."""
from typing import Annotated

from fastapi import Header, HTTPException

from backend.models import User
from backend.repositories import get_user


def get_current_user(
    demo_user_id: Annotated[str | None, Header(alias="X-Demo-User-Id")] = None,
) -> User:
    if demo_user_id is None:
        raise HTTPException(status_code=401, detail="Select a demo user")
    user = get_user(demo_user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Unknown demo user")
    return user
