"""Separate sign-in/calendar consent. Provider tokens never reach the browser."""
import asyncio
import secrets
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from backend import accounts, settings
from backend.models import AuthStart, AuthStatus
from backend.services import google_auth

router=APIRouter(tags=['authentication'])


def verify_origin(request: Request) -> None:
    if request.headers.get('origin')!=settings.frontend_url():raise HTTPException(403,'Request origin is not allowed')


@router.get('/auth/status',response_model=AuthStatus)
def status(request: Request) -> AuthStatus:
    user=accounts.session_user(request.cookies.get(accounts.SESSION_COOKIE)) if settings.mode()=='google' else None
    try:settings.google_config();accounts.cipher();configured=True
    except (ValueError,OSError,KeyError):configured=False
    row=accounts.account(user.id) if user else None
    return AuthStatus(mode=settings.mode(),configured=configured,authenticated=user is not None,user=user,
        calendar_mode='google' if settings.mode()=='google' else 'mock',calendar_connected=bool(row and row['credentials']))


@router.post('/auth/google/start')
def start(body: AuthStart,request: Request,response: Response):
    verify_origin(request)
    if settings.mode()!='google':raise HTTPException(409,'Start the backend in Google mode to use real accounts')
    user=accounts.session_user(request.cookies.get(accounts.SESSION_COOKIE))
    if body.purpose=='calendar' and user is None:raise HTTPException(401,'Sign in before connecting your calendar')
    try:
        ZoneInfo(body.timezone)
        url,data=google_auth.prepare(body.purpose,user.id if user else None,body.timezone)
        browser=secrets.token_urlsafe(32)
        accounts.save_oauth(data['state'],browser,data)
    except (ValueError,ZoneInfoNotFoundError,OSError,KeyError) as error:
        raise HTTPException(503,'Google sign-in is not configured; check backend setup') from error
    response.set_cookie(accounts.OAUTH_COOKIE,browser,httponly=True,secure=settings.secure_cookies(),samesite='lax',max_age=600,path='/')
    return {'authorization_url':url}


@router.get('/calendar/oauth/callback')
async def callback(request: Request,state: str='',code: str='',error: str | None=None):
    try:
        if settings.mode()!='google':raise ValueError('Google mode is disabled')
        data=accounts.consume_oauth(state,request.cookies.get(accounts.OAUTH_COOKIE))
        if error or not code:raise ValueError('Google authorization was declined')
        if data['purpose']=='calendar':
            user=accounts.session_user(request.cookies.get(accounts.SESSION_COOKIE))
            if user is None or user.id!=data['user_id']:raise ValueError('Sign-in session changed; reconnect your calendar')
        claims,tokens=await asyncio.wait_for(asyncio.to_thread(google_auth.exchange,code,data),timeout=60)
        if data['purpose']=='calendar':
            account=accounts.account(data['user_id'])
            if not account or account['subject']!=claims['sub']:raise ValueError('Choose the same Google account you signed in with')
            accounts.save_credentials(data['user_id'],tokens)
        else:
            user=accounts.login_user(claims,data['timezone'])
        response=RedirectResponse(settings.frontend_url()+'/?auth=success',status_code=303)
        if data['purpose']=='login':
            accounts.delete_session(request.cookies.get(accounts.SESSION_COOKIE))
            token=accounts.create_session(user.id)
            response.set_cookie(accounts.SESSION_COOKIE,token,httponly=True,secure=settings.secure_cookies(),samesite='lax',max_age=86400*7,path='/')
    except Exception:
        # Do not include authorization codes, tokens, or provider errors in URLs.
        response=RedirectResponse(settings.frontend_url()+'/?auth=failed',status_code=303)
    response.delete_cookie(accounts.OAUTH_COOKIE,path='/')
    return response


@router.post('/auth/logout',status_code=204)
def logout(request: Request,response: Response):
    verify_origin(request)
    accounts.delete_session(request.cookies.get(accounts.SESSION_COOKIE))
    response.delete_cookie(accounts.SESSION_COOKIE,path='/')
