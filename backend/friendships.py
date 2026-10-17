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


def respond_to_friend_request(
    request_id: str, recipient_id: str, decision: str,
) -> FriendRequest:
    """Answer once as recipient; repeating the same decision is idempotent.

    Callers derive recipient_id from identity. LookupError means missing,
    PermissionError means non-recipient, and ValueError means invalid/conflicting
    decision. A write transaction serializes the read/check/update sequence.
    """
    if decision not in ("accept", "decline"):
        raise ValueError("Decision must be accept or decline")
    new_status = "accepted" if decision == "accept" else "declined"

    with connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT * FROM friend_requests WHERE id = ?", (request_id,),
        ).fetchone()
        if row is None:
            raise LookupError("Friend request not found")

        request = FriendRequest.model_validate(dict(row))
        if request.recipient_id != recipient_id:
            raise PermissionError("Only the recipient can respond")
        if request.status == new_status:
            return request
        if request.status != "pending":
            raise ValueError("Friend request has already been answered")

        updated = FriendRequest.model_validate({
            **request.model_dump(),
            "status": new_status,
            "responded_at": datetime.now(timezone.utc),
        })
        connection.execute(
            """
            UPDATE friend_requests SET status = ?, responded_at = ?
            WHERE id = ?
            """,
            (updated.status, updated.responded_at.isoformat(), updated.id),
        )
    return updated


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


def remove_friendship(request_id: str, user_id: str) -> FriendRequest:
    """Either participant may end this exact friendship, retaining its history."""
    with connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT * FROM friend_requests WHERE id = ?", (request_id,),
        ).fetchone()
        if row is None:
            raise LookupError("Friendship not found")
        request = FriendRequest.model_validate(dict(row))
        if user_id not in (request.sender_id, request.recipient_id):
            raise PermissionError("Only participants can remove this friendship")
        if request.status == "removed":
            return request
        if request.status != "accepted":
            raise ValueError("This request is not an active friendship")
        updated = FriendRequest.model_validate({**request.model_dump(), "status": "removed"})
        connection.execute(
            "UPDATE friend_requests SET status = ? WHERE id = ?", ("removed", request_id),
        )
    return updated
