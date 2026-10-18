"""Reset only generated mock history, with a recoverable database backup."""
import sqlite3
import pytest
from backend.database import connect
from backend.hangouts import create_hangout_request
from backend.scripts.reset_demo_plans import reset_demo_plans
from backend.models import User
from backend.repositories import get_user,save_user


def test_reset_backs_up_history_and_preserves_settings(request_record):
    create_hangout_request(request_record)
    with connect() as connection:
        before={name:connection.execute(f'SELECT COUNT(*) FROM {name}').fetchone()[0] for name in ['users','social_windows','friend_requests']}
    backup,counts=reset_demo_plans()
    assert counts['hangout_requests']==1 and backup.exists()
    with sqlite3.connect(backup) as connection:assert connection.execute('SELECT COUNT(*) FROM hangout_requests').fetchone()[0]==1
    with connect() as connection:
        assert connection.execute('SELECT COUNT(*) FROM hangout_requests').fetchone()[0]==0
        assert {name:connection.execute(f'SELECT COUNT(*) FROM {name}').fetchone()[0] for name in before}==before


def test_reset_refuses_real_profiles(seeded_database):
    user=get_user('demo-zaynah')
    save_user(User.model_validate(user.model_dump()|{'id':'user-'+'a'*32,'is_demo':False,'community':None}))
    with pytest.raises(ValueError):reset_demo_plans()
