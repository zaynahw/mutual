"""SQLite connection and initial tables; no API or authorization logic here.

Records are stored as Pydantic-produced JSON, with IDs and ownership in SQL
columns. Callers must validate records and keep those columns consistent with
the JSON. Reading JSON back through Pydantic revalidates its structure.
"""
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


DEFAULT_DATABASE_PATH = Path(__file__).resolve().parent / "mutual.db"


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """Commit on success, roll back on failure, and always close the connection.

    The path is read on every call so tests can select a temporary database.
    Set MUTUAL_DATABASE_PATH in the shell; this module does not load .env files.
    """
    database_path = os.getenv("MUTUAL_DATABASE_PATH", str(DEFAULT_DATABASE_PATH))
    connection = sqlite3.connect(database_path)
    try:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


FRIEND_REQUESTS_TABLE = """
CREATE TABLE IF NOT EXISTS friend_requests (
    id TEXT PRIMARY KEY NOT NULL,
    sender_id TEXT NOT NULL,
    recipient_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'accepted', 'declined', 'removed')),
    created_at TEXT NOT NULL,
    responded_at TEXT,
    FOREIGN KEY (sender_id) REFERENCES users(id),
    FOREIGN KEY (recipient_id) REFERENCES users(id),
    CHECK (sender_id != recipient_id),
    CHECK (
        (status = 'pending' AND responded_at IS NULL)
        OR
        (status IN ('accepted', 'declined', 'removed') AND responded_at IS NOT NULL)
    )
);
"""

FRIEND_PAIR_INDEX = """
CREATE UNIQUE INDEX IF NOT EXISTS unique_active_friend_pair
ON friend_requests (
    min(sender_id, recipient_id),
    max(sender_id, recipient_id)
)
WHERE status IN ('pending', 'accepted');
"""


def initialize_database() -> None:
    """Create tables and indexes without replacing existing data.

    Includes a transactional upgrade of the original friendship status constraint.
    Future schema changes will need explicit migrations too.
    """
    with connect() as connection:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY NOT NULL,
                data TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS social_windows (
                id TEXT PRIMARY KEY NOT NULL,
                user_id TEXT NOT NULL,
                data TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE INDEX IF NOT EXISTS social_windows_user_id
            ON social_windows(user_id);

            CREATE TABLE IF NOT EXISTS hangout_requests (
                id TEXT PRIMARY KEY NOT NULL,
                requester_id TEXT NOT NULL,
                invitee_id TEXT NOT NULL,
                data TEXT NOT NULL,
                FOREIGN KEY (requester_id) REFERENCES users(id),
                FOREIGN KEY (invitee_id) REFERENCES users(id),
                CHECK (requester_id != invitee_id)
            );

            CREATE INDEX IF NOT EXISTS hangout_requests_requester
            ON hangout_requests(requester_id);

            CREATE INDEX IF NOT EXISTS hangout_requests_invitee
            ON hangout_requests(invitee_id);

        """)

        # SQLite cannot alter a CHECK constraint in place. Serialize setup and
        # rebuild only the old friendship table, retaining every existing row.
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'friend_requests'"
        ).fetchone()
        if row is not None and "'removed'" not in row["sql"]:
            connection.execute(FRIEND_REQUESTS_TABLE.replace(
                "CREATE TABLE IF NOT EXISTS friend_requests", "CREATE TABLE friend_requests_upgrade",
            ))
            connection.execute("""
                INSERT INTO friend_requests_upgrade
                (id, sender_id, recipient_id, status, created_at, responded_at)
                SELECT id, sender_id, recipient_id, status, created_at, responded_at
                FROM friend_requests
            """)
            connection.execute("DROP TABLE friend_requests")
            connection.execute("ALTER TABLE friend_requests_upgrade RENAME TO friend_requests")
        else:
            connection.execute(FRIEND_REQUESTS_TABLE)
        connection.execute(FRIEND_PAIR_INDEX)


if __name__ == "__main__":
    initialize_database()
