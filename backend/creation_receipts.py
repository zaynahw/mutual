"""Payload-bound creation receipts; callers save records and receipts atomically."""
import hashlib
import json

from backend.database import connect


def payload_hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def read_receipt(connection, actor_id: str, key: str | None, operation: str, payload: dict) -> str | None:
    if key is None:
        return None
    row = connection.execute(
        'SELECT operation, payload_hash, response FROM creation_receipts WHERE actor_id = ? AND key = ?',
        (actor_id, key),
    ).fetchone()
    if row is None:
        return None
    if row['operation'] != operation or row['payload_hash'] != payload_hash(payload):
        raise ValueError('This creation key was already used for different input')
    return row['response']


def get_receipt(actor_id: str, key: str | None, operation: str, payload: dict) -> str | None:
    with connect() as connection:
        return read_receipt(connection, actor_id, key, operation, payload)


def save_receipt(connection, actor_id: str, key: str | None, operation: str, payload: dict, response: str) -> None:
    if key is not None:
        connection.execute(
            'INSERT INTO creation_receipts (actor_id, key, operation, payload_hash, response) VALUES (?, ?, ?, ?, ?)',
            (actor_id, key, operation, payload_hash(payload), response),
        )
