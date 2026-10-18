"""Internal persistence helpers; callers enforce permissions before exposure.

Initialize the database before use. User results include private settings and
window results include private/matching-only windows. These are not public API
responses. SQLite integrity errors propagate for callers to handle.
"""
from backend.database import connect
from backend.models import MatchingSettings, SocialWindow, User


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


def update_preference_note(user_id: str, note: str) -> User:
    """Read current settings and update only the owner's note atomically."""
    with connect() as connection:
        connection.execute('BEGIN IMMEDIATE')
        row = connection.execute('SELECT data FROM users WHERE id = ?', (user_id,)).fetchone()
        if row is None:
            raise LookupError('User not found')
        current = User.model_validate_json(row['data'])
        data = current.model_dump()
        data['preferences']['soft_preference_note'] = note
        updated = User.model_validate(data)
        connection.execute('UPDATE users SET data = ? WHERE id = ?', (updated.model_dump_json(), user_id))
        return updated


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


def update_social_window(window: SocialWindow) -> bool:
    """Update only when the ID and owner both match; never change ownership."""
    with connect() as connection:
        result = connection.execute(
            "UPDATE social_windows SET data = ? WHERE id = ? AND user_id = ?",
            (window.model_dump_json(), window.id, window.user_id),
        )
    return result.rowcount == 1


def delete_social_window(window_id: str, user_id: str) -> bool:
    with connect() as connection:
        result = connection.execute(
            "DELETE FROM social_windows WHERE id = ? AND user_id = ?",
            (window_id, user_id),
        )
    return result.rowcount == 1


def update_matching_settings(user_id: str, settings: MatchingSettings) -> User:
    with connect() as connection:
        connection.execute('BEGIN IMMEDIATE')
        row = connection.execute('SELECT data FROM users WHERE id = ?', (user_id,)).fetchone()
        if row is None:
            raise LookupError('User not found')
        data = User.model_validate_json(row['data']).model_dump()
        data['matching'] = settings.model_dump()
        updated = User.model_validate(data)
        connection.execute('UPDATE users SET data = ? WHERE id = ?', (updated.model_dump_json(), user_id))
        return updated


def update_community_membership(user_id: str, community: str | None) -> User:
    """Explicit opt-in to the open MVP community; not institutional verification."""
    if community not in (None, 'georgia_tech'):
        raise ValueError('Unknown community')
    with connect() as connection:
        connection.execute('BEGIN IMMEDIATE')
        row = connection.execute('SELECT data FROM users WHERE id = ?', (user_id,)).fetchone()
        if row is None:
            raise LookupError('User not found')
        user = User.model_validate_json(row['data'])
        updated = user.model_copy(update={'community':community})
        connection.execute('UPDATE users SET data = ? WHERE id = ?', (updated.model_dump_json(),user_id))
    return updated
