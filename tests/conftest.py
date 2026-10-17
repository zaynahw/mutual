"""Function-scoped fixtures: every test receives its own SQLite file.

Use database_path for a nonexistent database, initialized_database for empty
schema, and seeded_database for demo records. No fixture seeds automatically.
"""
import json

import pytest
from fastapi.testclient import TestClient

from backend.database import initialize_database
from backend.main import app
from backend.models import HangoutRequest
from backend.seed import DEFAULT_FIXTURE_PATH, seed_demo_data


@pytest.fixture
def database_path(tmp_path, monkeypatch):
    path = tmp_path / 'test.db'
    monkeypatch.setenv('MUTUAL_DATABASE_PATH', str(path))
    return path


@pytest.fixture
def initialized_database(database_path):
    initialize_database()
    return database_path


@pytest.fixture
def seeded_database(database_path):
    seed_demo_data()
    return database_path


@pytest.fixture
def client(seeded_database):
    with TestClient(app) as client:
        yield client


@pytest.fixture
def request_record(seeded_database):
    data = json.loads(DEFAULT_FIXTURE_PATH.read_text())
    return HangoutRequest.model_validate(data['request'])
