"""Explicit runtime modes and Google configuration; no secrets in responses."""
import json
import os
from pathlib import Path
from urllib.parse import urlparse


def mode() -> str:
    value = os.getenv('MUTUAL_MODE','demo')
    if value not in ('demo','google'): raise ValueError('MUTUAL_MODE must be demo or google')
    return value


def frontend_url() -> str:
    value = os.getenv('FRONTEND_URL','http://localhost:5173').rstrip('/')
    parsed = urlparse(value)
    if parsed.scheme not in ('http','https') or not parsed.netloc or parsed.path:
        raise ValueError('FRONTEND_URL must be an origin without a path')
    return value


def secure_cookies() -> bool:
    return os.getenv('COOKIE_SECURE','0') == '1'


def google_config() -> dict:
    client_id, secret = os.getenv('GOOGLE_CLIENT_ID'), os.getenv('GOOGLE_CLIENT_SECRET')
    path = os.getenv('GOOGLE_CREDENTIALS_FILE')
    if path and not (client_id and secret):
        data = json.loads(Path(path).read_text())['web']
        client_id, secret = data['client_id'],data['client_secret']
    if not client_id or not secret: raise ValueError('Google OAuth credentials are not configured')
    return {'web':{'client_id':client_id,'client_secret':secret,
        'auth_uri':'https://accounts.google.com/o/oauth2/auth',
        'token_uri':'https://oauth2.googleapis.com/token',
        'redirect_uris':[redirect_uri()]}}


def redirect_uri() -> str:
    return os.getenv('GOOGLE_REDIRECT_URI','http://localhost:8000/calendar/oauth/callback')
