"""Internal friendship persistence queries, independent of HTTP routes."""
from datetime import datetime, timezone
from uuid import uuid4

from backend.database import connect
from backend.models import FriendRequest


def create_friend_request(sender_id: str, recipient_id: str) -> FriendRequest:
    """Insert a pending request. Callers must derive sender from identity.

    Pydantic rejects self-requests. SQLite integrity errors propagate for
    unknown users or duplicate active pairs; routes will map these to errors.
    """
    request = FriendRequest(
        id=f"friend-{uuid4()}",
        sender_id=sender_id,
        recipient_id=recipient_id,
        created_at=datetime.now(timezone.utc),
    )
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO friend_requests (
                id, sender_id, recipient_id, status, created_at, responded_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                request.id, request.sender_id, request.recipient_id,
                request.status, request.created_at.isoformat(), None,
            ),
        )
    return request


def list_friend_requests(user_id: str) -> list[FriendRequest]:
    """Load incoming/outgoing history; callers supply the authenticated/demo ID."""
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT * FROM friend_requests
            WHERE sender_id = ? OR recipient_id = ?
            ORDER BY created_at, id
            """,
            (user_id, user_id),
        ).fetchall()
    return [FriendRequest.model_validate(dict(row)) for row in rows]


def are_friends(user_a: str, user_b: str) -> bool:
    """An accepted request establishes friendship, regardless of sender."""
    first_id, second_id = sorted([user_a, user_b])
    with connect() as connection:
        row = connection.execute(
            """
            SELECT 1
            FROM friend_requests
            WHERE status = 'accepted'
              AND min(sender_id, recipient_id) = ?
              AND max(sender_id, recipient_id) = ?
            LIMIT 1
            """,
            (first_id, second_id),
        ).fetchone()
    return row is not None
