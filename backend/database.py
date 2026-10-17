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


def initialize_database() -> None:
    """Create tables and indexes without replacing existing data.

    This is initial setup, not a migration system. Further tables will be added
    as hangout requests and approval persistence are implemented.
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

            CREATE TABLE IF NOT EXISTS friend_requests (
                id TEXT PRIMARY KEY NOT NULL,
                sender_id TEXT NOT NULL,
                recipient_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'accepted', 'declined')),
                created_at TEXT NOT NULL,
                responded_at TEXT,
                FOREIGN KEY (sender_id) REFERENCES users(id),
                FOREIGN KEY (recipient_id) REFERENCES users(id),
                CHECK (sender_id != recipient_id),
                CHECK (
                    (status = 'pending' AND responded_at IS NULL)
                    OR
                    (status IN ('accepted', 'declined') AND responded_at IS NOT NULL)
                )
            );

            CREATE UNIQUE INDEX IF NOT EXISTS unique_active_friend_pair
            ON friend_requests (
                min(sender_id, recipient_id),
                max(sender_id, recipient_id)
            )
            WHERE status IN ('pending', 'accepted');
        """)


if __name__ == "__main__":
    initialize_database()
