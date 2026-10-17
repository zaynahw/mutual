"""Demo seeding must be repeatable, preserve edits, and fail atomically."""
import json
import sqlite3

import pytest
from pydantic import ValidationError

from backend.database import connect, initialize_database
from backend.models import User
from backend.repositories import get_user, list_social_windows, list_users, save_user
from backend.seed import DEFAULT_FIXTURE_PATH, seed_demo_data


def test_seed_inserts_four_users_and_five_windows_once(database_path):
    assert seed_demo_data() == (4, 5)
    assert {user.id for user in list_users()} == {
        "demo-zaynah", "demo-daniella", "demo-kusum", "demo-mariann",
    }
    assert sum(len(list_social_windows(user.id)) for user in list_users()) == 5
    assert seed_demo_data() == (0, 0)
    assert len(list_users()) == 4


def test_reseed_preserves_user_edits(database_path):
    seed_demo_data()
    user = get_user("demo-zaynah")
    updated = User.model_validate(user.model_dump() | {"display_name": "Zaynah edited (demo)"})
    save_user(updated)
    assert seed_demo_data() == (0, 0)
    assert get_user(updated.id) == updated


def test_reseed_preserves_window_edits(database_path):
    seed_demo_data()
    window = list_social_windows("demo-zaynah")[0]
    updated = window.model_copy(update={"sharing_mode": "matching_only"})
    with connect() as connection:
        connection.execute("UPDATE social_windows SET data = ? WHERE id = ?",
                           (updated.model_dump_json(), updated.id))
    seed_demo_data()
    assert updated in list_social_windows("demo-zaynah")


def test_invalid_fixture_is_rejected_before_database_creation(database_path, tmp_path):
    data = json.loads(DEFAULT_FIXTURE_PATH.read_text())
    data["social_windows"][0]["allowed_activities"] = ["unsupported"]
    fixture = tmp_path / "invalid.json"
    fixture.write_text(json.dumps(data))
    with pytest.raises(ValidationError):
        seed_demo_data(fixture)
    assert not database_path.exists()


def test_unknown_owner_rolls_back_new_records_and_preserves_existing(database_path, tmp_path):
    initialize_database()
    data = json.loads(DEFAULT_FIXTURE_PATH.read_text())
    existing = User.model_validate(data["users"][0])
    save_user(existing)
    data["social_windows"][-1]["user_id"] = "demo-missing"
    fixture = tmp_path / "unknown-owner.json"
    fixture.write_text(json.dumps(data))
    with pytest.raises(sqlite3.IntegrityError):
        seed_demo_data(fixture)
    assert list_users() == [existing]
    with connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM social_windows").fetchone()[0] == 0
