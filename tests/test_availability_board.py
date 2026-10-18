"""Discovery exposes only published social windows, never calendars/private profiles."""
from datetime import datetime, timedelta, timezone

from backend.friendships import create_friend_request, respond_to_friend_request, remove_friendship
from backend.models import SocialWindow, VisibilityPolicy
from backend.repositories import create_social_window, get_user, save_user

A, B = 'demo-zaynah', 'demo-daniella'


def window(owner=A, audience='community', mode='visible', suffix='', selected=None, offset=1):
    start = datetime.now(timezone.utc) + timedelta(days=offset)
    result = SocialWindow(id='board-'+owner+audience+mode+suffix, user_id=owner,
        start=start, end=start+timedelta(hours=1), allowed_activities=['coffee'],
        visibility=VisibilityPolicy(audience=audience,selected_friend_ids=selected or []),sharing_mode=mode)
    create_social_window(result)
    return result


def read(client, viewer=B):
    now = datetime.now(timezone.utc)
    return client.get('/availability-board', params={'start':now.isoformat(),'end':(now+timedelta(days=7)).isoformat()},
                      headers={'X-Demo-User-Id':viewer})


def test_board_published_only_with_private_projection_and_no_provider_reads(client):
    visible = window()
    window(audience='private')
    window(mode='matching_only')
    window(suffix='past',offset=-2)
    response = read(client)
    assert response.status_code == 200
    cards = [c for c in response.json() if c['window']['id'].startswith('board-')]
    assert [c['window']['id'] for c in cards] == [visible.id]
    assert set(cards[0]['owner']) == {'id','display_name','is_demo','community'}
    assert 'calendar_busy' not in response.text and 'preferences' not in response.text
    assert 'selected_friend_ids' not in response.text
    own = [c for c in read(client,A).json() if c['window']['id'].startswith('board-')]
    assert len(own) == 1  # owner's private/matching-only windows aren't published either


def test_board_community_requires_membership_and_demo_real_separation(client):
    window()
    user = get_user(B)
    save_user(user.model_copy(update={'community':None}))
    assert not [c for c in read(client).json() if c['owner']['id'] == A]
    save_user(user.model_copy(update={'community':'georgia_tech','is_demo':False}))
    # A demo caller must never see a real owner's windows.
    window(owner=B)
    assert all(c['owner']['id'] != B for c in read(client,A).json())


def test_board_friend_visibility_rechecks_current_relationship(client):
    window(audience='friends')
    window(audience='selected_friends', selected=[B])
    assert not [c for c in read(client).json() if c['window']['id'].startswith('board-')]
    friend = create_friend_request(A,B)
    respond_to_friend_request(friend.id,B,'accept')
    assert len([c for c in read(client).json() if c['window']['id'].startswith('board-')]) == 2
    remove_friendship(friend.id,A)
    assert not [c for c in read(client).json() if c['window']['id'].startswith('board-')]


def test_board_rejects_unauthenticated_and_unbounded_searches(client):
    now = datetime.now(timezone.utc)
    params={'start':now.isoformat(),'end':(now+timedelta(days=15)).isoformat()}
    assert client.get('/availability-board',params=params).status_code == 401
    assert client.get('/availability-board',params=params,headers={'X-Demo-User-Id':A}).status_code == 422


def test_open_community_choice_is_explicit_owner_only_and_preserves_private_settings(client):
    owner=get_user(B)
    save_user(owner.model_copy(update={'community':None}))
    window()
    assert not [c for c in read(client).json() if c['owner']['id']==A]
    before=client.get('/users/me',headers={'X-Demo-User-Id':B}).json()
    assert client.patch('/users/me/community',json={'community':'georgia_tech'}).status_code==401
    response=client.patch('/users/me/community',headers={'X-Demo-User-Id':B},json={'community':'georgia_tech'})
    assert response.status_code==200
    for field in ['preferences','hard_constraints','calendar_sharing','matching']:
        assert response.json()[field]==before[field]
    assert [c for c in read(client).json() if c['owner']['id']==A]
    for invalid in [{'community':'other'},{'community':'georgia_tech','user_id':A}]:
        assert client.patch('/users/me/community',headers={'X-Demo-User-Id':B},json=invalid).status_code==422
