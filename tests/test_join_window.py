"""Shared-window join requests require visibility, free/busy, and two approvals."""
from datetime import datetime, timedelta, timezone

import pytest

from backend.dependencies import get_calendar_adapter
from backend.friendships import create_friend_request, respond_to_friend_request, remove_friendship
from backend.hangouts import list_hangout_requests
from backend.main import app
from backend.models import BusyInterval, SocialWindow, VisibilityPolicy
from backend.proposals import get_proposal_response, record_decision
from backend.repositories import create_social_window, delete_social_window, get_user, save_user, update_social_window
from backend.services.calendar_adapter import MockCalendarAdapter
from backend.services.candidates import build_candidates

A,B='demo-zaynah','demo-daniella'


@pytest.fixture
def ready(client):
    friendship=create_friend_request(A,B)
    respond_to_friend_request(friendship.id,B,'accept')
    start=(datetime.now(timezone.utc)+timedelta(days=1)).replace(hour=14,minute=0,second=0,microsecond=0)
    window=SocialWindow(id='join-test-window',user_id=B,start=start,end=start+timedelta(hours=2),
                        allowed_activities=['coffee'],visibility=VisibilityPolicy(audience='friends'))
    create_social_window(window)
    app.dependency_overrides[get_calendar_adapter]=lambda:MockCalendarAdapter()
    yield client,window,friendship
    app.dependency_overrides.pop(get_calendar_adapter,None)


def body(window):
    return {'activity':'coffee','slot':{'start':window.start.isoformat(),'end':(window.start+timedelta(minutes=30)).isoformat()}}


def join(client,window,key='join-test',uid=A,payload=None):
    return client.post(f'/availability-board/{B}/{window.id}/join',json=payload or body(window),headers={
        'X-Demo-User-Id':uid,'Idempotency-Key':key})


def test_join_saves_exact_pending_plan_without_approvals_and_replays(ready):
    client,window,_=ready
    first=join(client,window)
    assert first.status_code==201,first.text
    data=first.json()
    assert data['request']['join_window_id']==window.id
    assert data['request']['requester_id']==A and data['request']['invitee_id']==B
    assert data['proposals'][0]['approvals']==[]
    assert data['proposals'][0]['proposal']['status']=='pending'
    assert join(client,window).json()==data
    assert len(list_hangout_requests(A))==1
    changed=body(window);changed['slot']['end']=(window.start+timedelta(minutes=60)).isoformat()
    assert join(client,window,payload=changed).status_code==409


def test_join_requires_visibility_friendship_and_strict_input(ready):
    client,window,friendship=ready
    assert join(client,window,uid='demo-kusum').status_code==404
    assert join(client,window,payload={**body(window),'approved_by':B}).status_code==422
    update_social_window(window.model_copy(update={'sharing_mode':'matching_only'}))
    assert join(client,window).status_code==404
    update_social_window(window)
    remove_friendship(friendship.id,A)
    assert join(client,window).status_code==404
    assert list_hangout_requests(A)==[]


def test_conflicts_and_out_of_window_times_fail_closed(ready):
    client,window,_=ready
    app.dependency_overrides[get_calendar_adapter]=lambda:MockCalendarAdapter([
        BusyInterval(user_id=A,start=window.start,end=window.end)])
    assert join(client,window).status_code==409
    app.dependency_overrides[get_calendar_adapter]=lambda:MockCalendarAdapter()
    invalid=body(window);invalid['slot']={'start':window.end.isoformat(),'end':(window.end+timedelta(minutes=30)).isoformat()}
    assert join(client,window,payload=invalid).status_code==409
    user=get_user(A)
    save_user(user.model_copy(update={'hard_constraints':user.hard_constraints.model_copy(update={'allowed_activities':['concert']})}))
    assert join(client,window).status_code==409
    assert list_hangout_requests(A)==[]


def test_permissions_changed_during_calendar_check_prevent_join(ready):
    client,window,_=ready
    class Changes(MockCalendarAdapter):
        async def get_busy(self,user_id,search):
            update_social_window(window.model_copy(update={'visibility':VisibilityPolicy(audience='private')}))
            return []
    app.dependency_overrides[get_calendar_adapter]=lambda:Changes()
    assert join(client,window).status_code==409
    assert list_hangout_requests(A)==[]


def test_join_source_is_rechecked_even_for_guided_owner(ready):
    client,window,_=ready
    user=get_user(B)
    save_user(user.model_copy(update={'matching':user.matching.model_copy(update={'mode':'calendar_guided'})}))
    data=join(client,window).json()
    proposal=data['proposals'][0]['proposal']
    record_decision(proposal['id'],A,'approve')
    assert get_proposal_response(proposal['id']).proposal.status=='pending'
    record_decision(proposal['id'],B,'approve')
    assert get_proposal_response(proposal['id']).proposal.status=='approved'
    delete_social_window(window.id,B)
    from backend.hangouts import get_hangout_request
    import asyncio
    assert asyncio.run(build_candidates(get_hangout_request(data['request']['id']),MockCalendarAdapter()))==[]


def test_nonfriend_can_join_community_window_but_not_friends_only(ready):
    client,window,friendship=ready
    remove_friendship(friendship.id,A)
    assert join(client,window).status_code==404
    window=window.model_copy(update={'visibility':VisibilityPolicy(audience='community'),'title':'Laufey concert'})
    update_social_window(window)
    result=join(client,window)
    assert result.status_code==201,result.text
    data=result.json()
    assert data['proposals'][0]['proposal']['title']=='Laufey concert'
    assert data['proposals'][0]['approvals']==[]
    assert data['request']['join_window_title']=='Laufey concert'


def test_community_membership_revocation_and_title_change_block_joined_plan(ready):
    import asyncio
    from backend.hangouts import get_hangout_request
    client,window,friendship=ready
    remove_friendship(friendship.id,A)
    window=window.model_copy(update={'visibility':VisibilityPolicy(audience='community'),'title':'Artist A'})
    update_social_window(window)
    data=join(client,window).json()
    request=get_hangout_request(data['request']['id'])
    update_social_window(window.model_copy(update={'title':'Artist B'}))
    assert asyncio.run(build_candidates(request,MockCalendarAdapter()))==[]
    update_social_window(window)
    assert client.patch('/users/me/community',headers={'X-Demo-User-Id':A},json={'community':None}).status_code==200
    assert asyncio.run(build_candidates(request,MockCalendarAdapter()))==[]
    assert join(client,window,key='after-leaving').status_code==404


def test_community_join_is_delivered_to_both_participants_inboxes_only(ready):
    client,window,friendship=ready
    remove_friendship(friendship.id,A)
    update_social_window(window.model_copy(update={'visibility':VisibilityPolicy(audience='community'),'title':'Community concert'}))
    sent=join(client,window)
    assert sent.status_code==201,sent.text
    request_id=sent.json()['request']['id']
    proposal_id=sent.json()['proposals'][0]['proposal']['id']
    for uid in (A,B):
        inbox=client.get('/hangout-requests/overview',headers={'X-Demo-User-Id':uid})
        assert inbox.status_code==200
        delivered=next(item for item in inbox.json() if item['request']['id']==request_id)
        assert delivered['proposals'][0]['proposal']['id']==proposal_id
        assert delivered['proposals'][0]['proposal']['title']=='Community concert'
        assert delivered['proposals'][0]['approvals']==[]
    other=client.get('/hangout-requests/overview',headers={'X-Demo-User-Id':'demo-kusum'})
    assert request_id not in {item['request']['id'] for item in other.json()}
    assert join(client,window).json()==sent.json()
    assert len(list_hangout_requests(A))==1
