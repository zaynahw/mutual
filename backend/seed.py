"""Populate missing demo users and social windows without overwriting edits."""
import json
from pathlib import Path

from backend.database import connect, initialize_database
from backend.models import SocialWindow, User


DEFAULT_FIXTURE_PATH = Path(__file__).resolve().parents[1] / "contracts" / "examples.json"


def seed_demo_data(fixture_path: Path = DEFAULT_FIXTURE_PATH) -> tuple[int, int]:
    data = json.loads(fixture_path.read_text())

    # Validate all seed records before making any database changes.
    users = [User.model_validate(record) for record in data["users"]]
    windows = [SocialWindow.model_validate(record) for record in data["social_windows"]]

    initialize_database()
    inserted_users = 0
    inserted_windows = 0

    # One transaction: if any insertion fails, all new records roll back.
    with connect() as connection:
        for user in users:
            result = connection.execute(
                """
                INSERT INTO users (id, data) VALUES (?, ?)
                ON CONFLICT(id) DO NOTHING
                """,
                (user.id, user.model_dump_json()),
            )
            inserted_users += result.rowcount

        for window in windows:
            result = connection.execute(
                """
                INSERT INTO social_windows (id, user_id, data) VALUES (?, ?, ?)
                ON CONFLICT(id) DO NOTHING
                """,
                (window.id, window.user_id, window.model_dump_json()),
            )
            inserted_windows += result.rowcount

    return inserted_users, inserted_windows


if __name__ == "__main__":
    users, windows = seed_demo_data()
    print(f"Inserted {users} demo users and {windows} social windows.")
