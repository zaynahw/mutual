"""Use isolated files, never the developer's demo database."""
import json
import sqlite3
from pathlib import Path

import pytest

from backend.database import connect, initialize_database
from backend.models import SocialWindow, User


def records():
    fixture = Path(__file__).resolve().parents[1] / "contracts/examples.json"
    data = json.loads(fixture.read_text())
    return User.model_validate(data["users"][0]), SocialWindow.model_validate(data["social_windows"][0])


def test_models_survive_connection_close_and_reinitialization(initialized_database):
    user, window = records()
    with connect() as connection:
        connection.execute("INSERT INTO users (id, data) VALUES (?, ?)",
                           (user.id, user.model_dump_json()))
        connection.execute("INSERT INTO social_windows (id, user_id, data) VALUES (?, ?, ?)",
                           (window.id, window.user_id, window.model_dump_json()))

    initialize_database()
    with connect() as connection:
        user_row = connection.execute("SELECT data FROM users WHERE id = ?", (user.id,)).fetchone()
        window_row = connection.execute("SELECT data FROM social_windows WHERE id = ?", (window.id,)).fetchone()
    assert User.model_validate_json(user_row["data"]) == user
    assert SocialWindow.model_validate_json(window_row["data"]) == window


def test_exception_rolls_back_and_closes_connection(initialized_database):
    user, _ = records()
    with pytest.raises(RuntimeError, match="cancel transaction"):
        with connect() as connection:
            connection.execute("INSERT INTO users (id, data) VALUES (?, ?)",
                               (user.id, user.model_dump_json()))
            raise RuntimeError("cancel transaction")
    with pytest.raises(sqlite3.ProgrammingError):
        connection.execute("SELECT 1")
    with connect() as check:
        assert check.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0


def test_unknown_owner_is_rejected(initialized_database):
    _, window = records()
    with pytest.raises(sqlite3.IntegrityError):
        with connect() as connection:
            connection.execute("INSERT INTO social_windows (id, user_id, data) VALUES (?, ?, ?)",
                               (window.id, window.user_id, window.model_dump_json()))


def test_duplicate_user_rolls_back_whole_transaction(initialized_database):
    user, _ = records()
    with pytest.raises(sqlite3.IntegrityError):
        with connect() as connection:
            for _ in range(2):
                connection.execute("INSERT INTO users (id, data) VALUES (?, ?)",
                                   (user.id, user.model_dump_json()))
    with connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0


def test_success_closes_connection(initialized_database):
    with connect() as connection:
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    with pytest.raises(sqlite3.ProgrammingError):
        connection.execute("SELECT 1")
