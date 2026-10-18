"""Google authorization-code flow. Identity comes from a verified ID token."""
import secrets
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from google.oauth2 import id_token
from backend import settings
from backend.accounts import credentials

IDENTITY_SCOPES = ['openid','https://www.googleapis.com/auth/userinfo.email','https://www.googleapis.com/auth/userinfo.profile']
CALENDAR_SCOPES = ['https://www.googleapis.com/auth/calendar.freebusy','https://www.googleapis.com/auth/calendar.events']


def flow_for(data: dict) -> Flow:
    flow=Flow.from_client_config(settings.google_config(),scopes=data['scopes'],state=data['state'],code_verifier=data['verifier'])
    flow.redirect_uri=settings.redirect_uri()
    return flow


def prepare(purpose: str,user_id: str | None,timezone: str) -> tuple[str,dict]:
    data={'purpose':purpose,'user_id':user_id,'timezone':timezone,'state':secrets.token_urlsafe(32),
          'nonce':secrets.token_urlsafe(32),'verifier':secrets.token_urlsafe(64),
          'scopes':IDENTITY_SCOPES+(CALENDAR_SCOPES if purpose=='calendar' else [])}
    flow=flow_for(data)
    url,_=flow.authorization_url(access_type='offline',prompt='consent' if purpose=='calendar' else 'select_account',nonce=data['nonce'])
    return url,data


def exchange(code: str,data: dict) -> tuple[dict,dict]:
    flow=flow_for(data)
    flow.fetch_token(code=code,timeout=30)
    creds=flow.credentials
    claims=id_token.verify_oauth2_token(creds.id_token,Request(),settings.google_config()['web']['client_id'])
    if claims.get('iss') not in ('accounts.google.com','https://accounts.google.com') or claims.get('nonce')!=data['nonce']:
        raise ValueError('Google identity verification failed')
    if not claims.get('sub') or not claims.get('email') or claims.get('email_verified') is not True:
        raise ValueError('A verified Google email is required')
    result={'token':creds.token,'refresh_token':creds.refresh_token,'token_uri':creds.token_uri,
            'client_id':creds.client_id,'client_secret':creds.client_secret,'scopes':list(creds.granted_scopes or creds.scopes or []),
            'expiry':creds.expiry.isoformat()+'Z' if creds.expiry and creds.expiry.tzinfo is None else creds.expiry.isoformat() if creds.expiry else None}
    if data['purpose']=='calendar':
        if not set(CALENDAR_SCOPES)<=set(result['scopes']):raise ValueError('Both calendar permissions are required')
        if not result['refresh_token']:
            try: result['refresh_token']=credentials(data['user_id']).get('refresh_token')
            except ValueError: pass
        if not result['refresh_token']:raise ValueError('Google did not grant offline calendar access; reconnect with consent')
    return claims,result
