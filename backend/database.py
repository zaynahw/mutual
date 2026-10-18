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

            CREATE TABLE IF NOT EXISTS proposals (
                id TEXT PRIMARY KEY NOT NULL,
                request_id TEXT NOT NULL,
                data TEXT NOT NULL,
                FOREIGN KEY (request_id) REFERENCES hangout_requests(id)
            );

            CREATE INDEX IF NOT EXISTS proposals_request
            ON proposals(request_id);

            CREATE TABLE IF NOT EXISTS approvals (
                proposal_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                decision TEXT NOT NULL CHECK (decision IN ('approve', 'decline')),
                decided_at TEXT NOT NULL,
                PRIMARY KEY (proposal_id, user_id),
                FOREIGN KEY (proposal_id) REFERENCES proposals(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS calendar_events (
                proposal_id TEXT PRIMARY KEY NOT NULL REFERENCES proposals(id),
                status TEXT NOT NULL CHECK (status IN ('creating', 'retryable', 'completed')),
                claim_token TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                event_id TEXT,
                external_started INTEGER NOT NULL DEFAULT 0 CHECK (external_started IN (0, 1)),
                CHECK ((status = 'completed' AND event_id IS NOT NULL)
                    OR (status != 'completed' AND event_id IS NULL))
            );

            CREATE TABLE IF NOT EXISTS hangout_intents (
                id TEXT PRIMARY KEY NOT NULL,
                owner_id TEXT NOT NULL REFERENCES users(id),
                data TEXT NOT NULL,
                request_id TEXT REFERENCES hangout_requests(id)
            );

            CREATE TABLE IF NOT EXISTS google_accounts (
                subject TEXT PRIMARY KEY NOT NULL,
                user_id TEXT UNIQUE NOT NULL REFERENCES users(id),
                email TEXT NOT NULL,
                credentials TEXT
            );
            CREATE TABLE IF NOT EXISTS auth_sessions (
                token_hash TEXT PRIMARY KEY NOT NULL,
                user_id TEXT NOT NULL REFERENCES users(id),
                expires_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS oauth_states (
                state_hash TEXT PRIMARY KEY NOT NULL,
                browser_hash TEXT NOT NULL,
                data TEXT NOT NULL,
                expires_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS creation_receipts (
                actor_id TEXT NOT NULL REFERENCES users(id),
                key TEXT NOT NULL,
                operation TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                response TEXT NOT NULL,
                PRIMARY KEY (actor_id, key)
            );

            CREATE TABLE IF NOT EXISTS calendar_event_keys (
                idempotency_key TEXT PRIMARY KEY NOT NULL,
                proposal_id TEXT NOT NULL REFERENCES proposals(id)
            );

        """)

        columns = {row['name'] for row in connection.execute('PRAGMA table_info(calendar_events)')}
        if 'external_started' not in columns:
            # Existing attempts may already have reached the provider. Be conservative.
            connection.execute('ALTER TABLE calendar_events ADD COLUMN external_started INTEGER NOT NULL DEFAULT 1')
            connection.commit()

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
