"""Google identities, encrypted provider credentials, and revocable opaque sessions."""
import hashlib
import json
import os
import secrets
import time
from uuid import uuid4
from cryptography.fernet import Fernet
from backend.database import connect
from backend.models import User, HardConstraints
from backend.repositories import get_user

SESSION_COOKIE = 'mutual_session'
OAUTH_COOKIE = 'mutual_oauth_browser'


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def cipher() -> Fernet:
    key = os.getenv('MUTUAL_TOKEN_KEY')
    if not key: raise ValueError('MUTUAL_TOKEN_KEY must be configured before connecting Google')
    return Fernet(key.encode())


def account(user_id: str):
    with connect() as connection:
        row=connection.execute('SELECT * FROM google_accounts WHERE user_id=?',(user_id,)).fetchone()
    return dict(row) if row else None


def save_credentials(user_id: str, data: dict) -> None:
    encrypted=cipher().encrypt(json.dumps(data).encode()).decode()
    with connect() as connection:
        updated=connection.execute('UPDATE google_accounts SET credentials=? WHERE user_id=?',(encrypted,user_id))
        if updated.rowcount!=1: raise LookupError('Google account not linked')


def credentials(user_id: str) -> dict:
    row=account(user_id)
    if not row or not row['credentials']: raise ValueError('Connect Google Calendar before checking availability')
    return json.loads(cipher().decrypt(row['credentials'].encode()))


def login_user(claims: dict, timezone: str) -> User:
    with connect() as connection:
        connection.execute('BEGIN IMMEDIATE')
        row=connection.execute('SELECT user_id FROM google_accounts WHERE subject=?',(claims['sub'],)).fetchone()
        if row:
            connection.execute('UPDATE google_accounts SET email=? WHERE subject=?',(claims['email'],claims['sub']))
            user_id=row['user_id']
        else:
            user=User(id='user-'+uuid4().hex,display_name=claims.get('name') or claims['email'].split('@')[0],
                is_demo=False,community='georgia_tech' if claims.get('hd')=='gatech.edu' else None,
                timezone=timezone,hard_constraints=HardConstraints(allowed_activities=['coffee','meal','walk','study','concert']))
            connection.execute('INSERT INTO users(id,data) VALUES (?,?)',(user.id,user.model_dump_json()))
            connection.execute('INSERT INTO google_accounts(subject,user_id,email) VALUES (?,?,?)',(claims['sub'],user.id,claims['email']))
            user_id=user.id
    return get_user(user_id)


def create_session(user_id: str) -> str:
    token=secrets.token_urlsafe(32)
    with connect() as connection:
        connection.execute('DELETE FROM auth_sessions WHERE expires_at<=?',(time.time(),))
        connection.execute('INSERT INTO auth_sessions VALUES (?,?,?)',(digest(token),user_id,time.time()+86400*7))
    return token


def session_user(token: str | None) -> User | None:
    if not token:return None
    with connect() as connection:
        row=connection.execute('SELECT user_id FROM auth_sessions WHERE token_hash=? AND expires_at>?',(digest(token),time.time())).fetchone()
    return get_user(row['user_id']) if row else None


def delete_session(token: str | None) -> None:
    if token:
        with connect() as connection: connection.execute('DELETE FROM auth_sessions WHERE token_hash=?',(digest(token),))


def save_oauth(state: str,browser: str,data: dict) -> None:
    encrypted=cipher().encrypt(json.dumps(data).encode()).decode()
    with connect() as connection:
        connection.execute('DELETE FROM oauth_states WHERE expires_at<=?',(time.time(),))
        connection.execute('INSERT INTO oauth_states VALUES (?,?,?,?)',(digest(state),digest(browser),encrypted,time.time()+600))


def consume_oauth(state: str,browser: str | None) -> dict:
    if not browser:raise ValueError('OAuth must finish in the browser that started it')
    with connect() as connection:
        connection.execute('BEGIN IMMEDIATE')
        row=connection.execute('SELECT * FROM oauth_states WHERE state_hash=?',(digest(state),)).fetchone()
        if not row or row['expires_at']<=time.time() or not secrets.compare_digest(row['browser_hash'],digest(browser)):
            raise ValueError('Invalid or expired sign-in request')
        connection.execute('DELETE FROM oauth_states WHERE state_hash=?',(digest(state),))
    return json.loads(cipher().decrypt(row['data'].encode()))
