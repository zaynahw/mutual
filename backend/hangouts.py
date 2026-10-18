"""Internal request persistence; routes must enforce participant access.

Initialize the database before use. These functions do not establish identity,
generate candidates, or call agents. SQLite integrity errors propagate.
"""
from backend.database import connect
from backend.models import HangoutRequest, HangoutOverview
from backend.creation_receipts import read_receipt, save_receipt
from backend.proposals import _read_response


def create_hangout_request(request: HangoutRequest, idempotency_key: str | None = None) -> HangoutRequest:
    """Insert only; columns and JSON come from the same validated record."""
    payload = request.model_dump(mode='json', exclude={'id', 'requester_id'})
    with connect() as connection:
        connection.execute('BEGIN IMMEDIATE')
        replay = read_receipt(connection, request.requester_id, idempotency_key, 'hangout', payload)
        if replay is not None:
            return HangoutRequest.model_validate_json(replay)
        connection.execute(
            """
            INSERT INTO hangout_requests (id, requester_id, invitee_id, data)
            VALUES (?, ?, ?, ?)
            """,
            (request.id, request.requester_id, request.invitee_id, request.model_dump_json()),
        )
        save_receipt(connection, request.requester_id, idempotency_key, 'hangout', payload, request.model_dump_json())
    return request


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


def list_hangout_overviews(user_id: str) -> list[HangoutOverview]:
    with connect() as connection:
        connection.execute('BEGIN')
        requests = connection.execute(
            'SELECT data FROM hangout_requests WHERE requester_id = ? OR invitee_id = ? ORDER BY id',
            (user_id, user_id),
        ).fetchall()
        result = []
        for row in requests:
            request = HangoutRequest.model_validate_json(row['data'])
            ids = connection.execute('SELECT id FROM proposals WHERE request_id = ? ORDER BY id', (request.id,)).fetchall()
            result.append(HangoutOverview(request=request, proposals=[_read_response(connection, item['id']) for item in ids]))
        return result
