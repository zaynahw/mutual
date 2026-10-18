"""Cookie identity, OAuth browser binding, durable encrypted tokens, and privacy."""
from urllib.parse import parse_qs,urlparse
from cryptography.fernet import Fernet
import pytest
from backend import accounts
from backend.database import connect
from backend.services import google_auth
from backend.models import User
from backend.services.permissions import can_access

ORIGIN={'Origin':'http://localhost:5173'}


@pytest.fixture
def google_client(client,monkeypatch):
    monkeypatch.setenv('MUTUAL_MODE','google')
    monkeypatch.setenv('GOOGLE_CLIENT_ID','test-client')
    monkeypatch.setenv('GOOGLE_CLIENT_SECRET','fake-secret')
    monkeypatch.setenv('MUTUAL_TOKEN_KEY',Fernet.generate_key().decode())
    yield client


def login(client,monkeypatch,subject='google-one',email='one@example.com'):
    result=client.post('/auth/google/start',headers=ORIGIN,json={'purpose':'login'})
    assert result.status_code==200,result.text
    query=parse_qs(urlparse(result.json()['authorization_url']).query)
    claims={'sub':subject,'email':email,'email_verified':True,'name':'Real Person'}
    monkeypatch.setattr(google_auth,'exchange',lambda code,data:(claims,{'token':'PRIVATE_ACCESS','refresh_token':'PRIVATE_REFRESH','scopes':google_auth.CALENDAR_SCOPES}))
    response=client.get('/calendar/oauth/callback',params={'code':'fake','state':query['state'][0]},follow_redirects=False)
    assert response.headers['location'].endswith('auth=success'),response.text
    return client.get('/auth/status').json(),query


def test_google_mode_rejects_demo_headers_and_missing_login(google_client):
    assert google_client.get('/users/me',headers={'X-Demo-User-Id':'demo-zaynah'}).status_code==401
    assert google_client.get('/auth/status').json()['authenticated'] is False


def test_real_login_session_overrides_spoofed_identity_and_logout_revokes(google_client,monkeypatch):
    status,_=login(google_client,monkeypatch)
    user=status['user']
    assert user['id'].startswith('user-') and not user['is_demo'] and user['community'] is None
    assert google_client.get('/users/me',headers={'X-Demo-User-Id':'demo-daniella'}).json()['id']==user['id']
    assert all(not p['is_demo'] for p in google_client.get('/users').json())
    assert google_client.patch('/users/me/preferences',json={'soft_preference_note':'private'}).status_code==403
    assert google_client.patch('/users/me/preferences',headers=ORIGIN,json={'soft_preference_note':'private'}).status_code==200
    assert google_client.post('/auth/logout',headers=ORIGIN).status_code==204
    assert google_client.get('/users/me').status_code==401


def test_oauth_start_requires_origin_and_callback_is_browser_bound_single_use(google_client,monkeypatch):
    assert google_client.post('/auth/google/start',json={}).status_code==403
    _,query=login(google_client,monkeypatch)
    replay=google_client.get('/calendar/oauth/callback',params={'state':query['state'][0],'code':'fake'},follow_redirects=False)
    assert replay.headers['location'].endswith('auth=failed')
    result=google_client.post('/auth/google/start',headers=ORIGIN,json={}).json()
    state=parse_qs(urlparse(result['authorization_url']).query)['state'][0]
    google_client.cookies.delete(accounts.OAUTH_COOKIE)
    response=google_client.get('/calendar/oauth/callback',params={'state':state,'code':'fake'},follow_redirects=False)
    assert response.headers['location'].endswith('auth=failed')


def test_calendar_connection_requires_same_google_account_and_tokens_are_encrypted(google_client,monkeypatch):
    status,_=login(google_client,monkeypatch)
    uid=status['user']['id']
    def connect_calendar(subject):
        response=google_client.post('/auth/google/start',headers=ORIGIN,json={'purpose':'calendar'})
        state=parse_qs(urlparse(response.json()['authorization_url']).query)['state'][0]
        monkeypatch.setattr(google_auth,'exchange',lambda *a:({'sub':subject},{'token':'PRIVATE_ACCESS','refresh_token':'PRIVATE_REFRESH'}))
        return google_client.get('/calendar/oauth/callback',params={'state':state,'code':'fake'},follow_redirects=False)
    assert connect_calendar('wrong-google-account').headers['location'].endswith('auth=failed')
    assert not accounts.account(uid)['credentials']
    assert connect_calendar('google-one').headers['location'].endswith('auth=success')
    assert google_client.get('/auth/status').json()['calendar_connected']
    assert 'PRIVATE' not in google_client.get('/auth/status').text
    assert 'PRIVATE' not in accounts.account(uid)['credentials']
    assert accounts.credentials(uid)['refresh_token']=='PRIVATE_REFRESH'


def test_repeated_signin_reuses_profile_and_preserves_preferences(google_client,monkeypatch):
    first,_=login(google_client,monkeypatch)
    google_client.patch('/users/me/preferences',headers=ORIGIN,json={'soft_preference_note':'Saved note'})
    second,_=login(google_client,monkeypatch)
    assert first['user']['id']==second['user']['id']
    assert second['user']['preferences']['soft_preference_note']=='Saved note'


def test_unverified_community_is_not_a_shared_audience(google_client,monkeypatch):
    first,_=login(google_client,monkeypatch)
    second,_=login(google_client,monkeypatch,subject='google-two',email='two@example.com')
    from backend.models import VisibilityPolicy
    assert not can_access(User.model_validate(first['user']),User.model_validate(second['user']),VisibilityPolicy(audience='community'))


def test_expired_session_and_oauth_state_are_rejected(google_client,monkeypatch):
    login(google_client,monkeypatch)
    with connect() as connection:connection.execute('UPDATE auth_sessions SET expires_at=0')
    assert google_client.get('/users/me').status_code==401
    accounts.save_oauth('state','browser',{'private':'verifier'})
    with connect() as connection:connection.execute('UPDATE oauth_states SET expires_at=0')
    with pytest.raises(ValueError): accounts.consume_oauth('state','browser')


def test_verified_token_nonce_and_calendar_grants_are_checked(monkeypatch):
    from types import SimpleNamespace
    from backend.services.google_auth import exchange
    monkeypatch.setenv('GOOGLE_CLIENT_ID','test-client')
    monkeypatch.setenv('GOOGLE_CLIENT_SECRET','fake-secret')
    creds=SimpleNamespace(id_token='fake-id-token',token='access',refresh_token='refresh',token_uri='https://oauth2.googleapis.com/token',client_id='test-client',client_secret='fake',expiry=None,granted_scopes=google_auth.IDENTITY_SCOPES,scopes=google_auth.IDENTITY_SCOPES)
    flow=SimpleNamespace(credentials=creds,fetch_token=lambda **kwargs:None)
    monkeypatch.setattr(google_auth,'flow_for',lambda data:flow)
    claims={'iss':'https://accounts.google.com','sub':'subject','email':'test@example.com','email_verified':True,'nonce':'wrong'}
    monkeypatch.setattr(google_auth.id_token,'verify_oauth2_token',lambda *a,**k:claims)
    data={'purpose':'login','nonce':'expected'}
    with pytest.raises(ValueError):exchange('code',data)
    claims['nonce']='expected'
    assert exchange('code',data)[0]['sub']=='subject'
    claims['email_verified']=False
    with pytest.raises(ValueError):exchange('code',data)
    claims['email_verified']=True
    with pytest.raises(ValueError):exchange('code',data|{'purpose':'calendar','user_id':'unused'})


def test_oauth_request_includes_pkce_and_nonce(google_client):
    response=google_client.post('/auth/google/start',headers=ORIGIN,json={})
    params=parse_qs(urlparse(response.json()['authorization_url']).query)
    assert params['code_challenge_method']==['S256']
    assert params['code_challenge'] and params['nonce']
    assert 'fake-secret' not in response.text
