"""Internal persistence helpers; callers enforce permissions before exposure.

Initialize the database before use. User results include private settings and
window results include private/matching-only windows. These are not public API
responses. SQLite integrity errors propagate for callers to handle.
"""
from backend.database import connect
from backend.models import SocialWindow, User


def save_user(user: User) -> None:
    """Insert a user, or replace the JSON for an existing user ID."""
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO users (id, data)
            VALUES (?, ?)
            ON CONFLICT(id)
            DO UPDATE SET data = excluded.data
            """,
            (user.id, user.model_dump_json()),
        )


def get_user(user_id: str) -> User | None:
    with connect() as connection:
        row = connection.execute(
            "SELECT data FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()

    if row is None:
        return None
    return User.model_validate_json(row["data"])


def list_users() -> list[User]:
    with connect() as connection:
        rows = connection.execute(
            "SELECT data FROM users ORDER BY id"
        ).fetchall()

    return [User.model_validate_json(row["data"]) for row in rows]


def create_social_window(window: SocialWindow) -> None:
    """Insert only: duplicate IDs and unknown owners are integrity errors."""
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO social_windows (id, user_id, data)
            VALUES (?, ?, ?)
            """,
            (window.id, window.user_id, window.model_dump_json()),
        )


def list_social_windows(user_id: str) -> list[SocialWindow]:
    """Load all owner windows without applying viewer visibility filters."""
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT data FROM social_windows
            WHERE user_id = ?
            ORDER BY id
            """,
            (user_id,),
        ).fetchall()

    return [SocialWindow.model_validate_json(row["data"]) for row in rows]
