"""Internal request persistence; routes must enforce participant access.

Initialize the database before use. These functions do not establish identity,
generate candidates, or call agents. SQLite integrity errors propagate.
"""
from backend.database import connect
from backend.models import HangoutRequest


def create_hangout_request(request: HangoutRequest) -> None:
    """Insert only; columns and JSON come from the same validated record."""
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO hangout_requests (id, requester_id, invitee_id, data)
            VALUES (?, ?, ?, ?)
            """,
            (request.id, request.requester_id, request.invitee_id, request.model_dump_json()),
        )


def get_hangout_request(request_id: str) -> HangoutRequest | None:
    with connect() as connection:
        row = connection.execute(
            "SELECT data FROM hangout_requests WHERE id = ?", (request_id,),
        ).fetchone()
    if row is None:
        return None
    return HangoutRequest.model_validate_json(row["data"])


def list_hangout_requests(user_id: str) -> list[HangoutRequest]:
    """Return incoming/outgoing requests in deterministic ID order."""
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT data FROM hangout_requests
            WHERE requester_id = ? OR invitee_id = ?
            ORDER BY id
            """,
            (user_id, user_id),
        ).fetchall()
    return [HangoutRequest.model_validate_json(row["data"]) for row in rows]
