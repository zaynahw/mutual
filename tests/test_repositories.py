"""Persistence behavior using isolated SQLite files."""
import json
import sqlite3
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.database import connect
from backend.models import SocialWindow, User
from backend.repositories import (
    create_social_window, get_user, list_social_windows, list_users, save_user,
)


@pytest.fixture
def records(initialized_database):
    fixture = Path(__file__).resolve().parents[1] / "contracts/examples.json"
    data = json.loads(fixture.read_text())
    return (
        [User.model_validate(value) for value in data["users"]],
        [SocialWindow.model_validate(value) for value in data["social_windows"]],
    )


def test_user_save_reload_and_update_without_duplicates(records):
    users, _ = records
    user = users[0]
    save_user(user)
    assert get_user(user.id) == user
    updated = User.model_validate(user.model_dump() | {"display_name": "Updated demo name"})
    save_user(updated)
    assert get_user(user.id) == updated
    assert list_users() == [updated]


def test_empty_and_missing_records(records):
    assert get_user("demo-missing") is None
    assert get_user("' OR 1=1 --") is None
    assert list_users() == []
    assert list_social_windows("demo-missing") == []


def test_users_have_predictable_order(records):
    users, _ = records
    for user in reversed(users):
        save_user(user)
    assert [user.id for user in list_users()] == sorted(user.id for user in users)


def test_window_owner_filter_and_private_storage(records):
    users, windows = records
    for user in users:
        save_user(user)
    for window in reversed(windows):
        create_social_window(window)
    for user in users:
        expected = sorted((window for window in windows if window.user_id == user.id), key=lambda w: w.id)
        assert list_social_windows(user.id) == expected
    private = SocialWindow.model_validate(windows[0].model_dump() | {
        "id": "private-window", "visibility": {"audience": "private"},
    })
    create_social_window(private)
    assert private in list_social_windows(private.user_id)


def test_window_integrity_errors_preserve_original(records):
    users, windows = records
    window = windows[0]
    with pytest.raises(sqlite3.IntegrityError):
        create_social_window(window)
    for user in users:
        save_user(user)
    create_social_window(window)
    changed_owner = SocialWindow.model_validate(window.model_dump() | {"user_id": users[1].id})
    with pytest.raises(sqlite3.IntegrityError):
        create_social_window(changed_owner)
    assert list_social_windows(window.user_id) == [window]
    assert list_social_windows(users[1].id) == []
    with connect() as connection:
        row = connection.execute("SELECT user_id, data FROM social_windows WHERE id = ?", (window.id,)).fetchone()
    assert row["user_id"] == json.loads(row["data"])["user_id"] == window.user_id


def test_reads_revalidate_stored_json(records):
    users, _ = records
    save_user(users[0])
    with connect() as connection:
        connection.execute("UPDATE users SET data = ? WHERE id = ?", ('{}', users[0].id))
    with pytest.raises(ValidationError):
        get_user(users[0].id)
