"""Backend integration: isolated agent contexts, consent, freshness, and receipts."""
import json

import pytest

from agent.local_llm import LocalLLMUnavailable
from agent.schemas import NegotiationResult
from backend.dependencies import get_agent_adapter, get_calendar_adapter
from backend.friendships import create_friend_request, respond_to_friend_request
from backend.hangouts import create_hangout_request
from backend.main import app
from backend.models import ProposalCreate
from backend.proposals import get_proposal_response, list_proposals_for_request, record_decision
from backend.repositories import get_user, save_user
from backend.services.agent_adapter import LocalAgentAdapter, MockAgentAdapter
from backend.services.calendar_adapter import MockCalendarAdapter


@pytest.fixture
def prepared(client, request_record):
    create_hangout_request(request_record)
    friend = create_friend_request(request_record.requester_id, request_record.invitee_id)
    respond_to_friend_request(friend.id, request_record.invitee_id, 'accept')
    app.dependency_overrides[get_calendar_adapter] = lambda: MockCalendarAdapter()
    app.dependency_overrides[get_agent_adapter] = lambda: MockAgentAdapter()
    yield client, request_record
    app.dependency_overrides.pop(get_calendar_adapter, None)
    app.dependency_overrides.pop(get_agent_adapter, None)


def negotiate(client, request, key='negotiate-key', user_id=None):
    return client.post(f'/hangout-requests/{request.id}/negotiate', headers={
        'X-Demo-User-Id': user_id or request.requester_id, 'Idempotency-Key':key,
    })


def test_mock_agreement_zero_approvals_and_retry_does_not_duplicate(prepared):
    client, request = prepared
    first = negotiate(client, request)
    assert first.status_code == 200
    result = first.json()
    assert result['source'] == 'mock' and result['status'] == 'agreed'
    pid = result['proposal']['id']
    assert get_proposal_response(pid).approvals == []
    assert get_proposal_response(pid).proposal.source == 'mock'
    assert negotiate(client,request).json() == result
    assert len(list_proposals_for_request(request.id)) == 1
    for uid in (request.requester_id, request.invitee_id):
        record_decision(pid,uid,'approve')
    assert negotiate(client,request).json() == result
    assert negotiate(client,request,key='new-attempt').status_code == 409


def test_live_path_with_stub_keeps_private_notes_and_reasons_isolated(prepared,monkeypatch):
    client, request = prepared
    for uid, note in [(request.requester_id,'REQUESTER_PRIVATE'),(request.invitee_id,'INVITEE_PRIVATE')]:
        user = get_user(uid)
        save_user(user.model_copy(update={'preferences':user.preferences.model_copy(update={'soft_preference_note':note})}))
    prompts = []
    class SpyModel:
        def chat(self,messages,**kwargs):
            prompts.append(messages[-1].content)
            return json.dumps({'decision':'propose' if len(prompts)==1 else 'accept', 'option_index':0,
                               'activity':'coffee','duration_minutes':30,
                               'reason':'REQUESTER_PRIVATE' if len(prompts)==1 else 'INVITEE_PRIVATE'})
    monkeypatch.setattr('agent.negotiate.LocalLLM',SpyModel)
    app.dependency_overrides[get_agent_adapter] = lambda: LocalAgentAdapter(fallback_on_error=False)
    response = negotiate(client,request)
    assert response.status_code == 200
    assert response.json()['source'] == 'local_agent'
    assert len(prompts)==2
    assert 'REQUESTER_PRIVATE' in prompts[0] and 'INVITEE_PRIVATE' not in prompts[0]
    assert 'INVITEE_PRIVATE' in prompts[1] and 'REQUESTER_PRIVATE' not in prompts[1]
    assert 'PRIVATE' not in response.text and 'reason' not in response.text
    assert get_proposal_response(response.json()['proposal']['id']).approvals == []


def test_local_failure_is_explicitly_labeled_fallback(prepared,monkeypatch):
    client, request = prepared
    class Failing:
        def chat(self,*args,**kwargs): raise LocalLLMUnavailable('private error')
    monkeypatch.setattr('agent.negotiate.LocalLLM',Failing)
    app.dependency_overrides[get_agent_adapter] = lambda: LocalAgentAdapter(fallback_on_error=True)
    result = negotiate(client,request)
    assert result.status_code == 200
    assert result.json()['source'] == result.json()['proposal']['source'] == 'demo_fallback'
    assert 'private error' not in result.text


def test_model_failure_without_fallback_is_generic_and_saves_nothing(prepared,monkeypatch):
    client, request = prepared
    class Failing:
        def chat(self,*args,**kwargs): raise LocalLLMUnavailable('credentials or private prompt')
    monkeypatch.setattr('agent.negotiate.LocalLLM',Failing)
    app.dependency_overrides[get_agent_adapter] = lambda: LocalAgentAdapter(fallback_on_error=False)
    response = negotiate(client,request)
    assert response.status_code == 502
    assert 'credentials' not in response.text
    assert list_proposals_for_request(request.id) == []


def test_stale_permissions_after_agent_call_block_save(prepared):
    client, request = prepared
    class Changing(MockAgentAdapter):
        async def negotiate(self,*args,**kwargs):
            result = await super().negotiate(*args,**kwargs)
            user = get_user(request.invitee_id)
            save_user(user.model_copy(update={'hard_constraints':user.hard_constraints.model_copy(update={'allowed_activities':['study']})}))
            return result
    app.dependency_overrides[get_agent_adapter] = lambda: Changing()
    assert negotiate(client,request).status_code == 409
    assert list_proposals_for_request(request.id) == []


def test_invalid_recommendation_and_exhaustion_do_not_create_proposals(prepared):
    client, request = prepared
    class Invalid(MockAgentAdapter):
        async def negotiate(self,*args,**kwargs):
            return NegotiationResult(status='agreed',proposal=ProposalCreate(activity='coffee',slot={
                'start':'2026-10-18T02:00:00Z','end':'2026-10-18T02:30:00Z',
            }))
    app.dependency_overrides[get_agent_adapter] = lambda: Invalid()
    assert negotiate(client,request).status_code == 409
    class Exhausted(MockAgentAdapter):
        async def negotiate(self,*args,**kwargs): return NegotiationResult(status='exhausted',reason='private note')
    app.dependency_overrides[get_agent_adapter] = lambda: Exhausted()
    response = negotiate(client,request,key='exhausted')
    assert response.status_code == 200 and response.json()['status']=='exhausted'
    assert response.json()['proposal'] is None and 'private note' not in response.text
    assert list_proposals_for_request(request.id) == []


def test_no_match_skips_inference_and_access_requires_participation_and_key(prepared):
    client, request = prepared
    path = f'/hangout-requests/{request.id}/negotiate'
    assert client.post(path).status_code == 401
    assert negotiate(client,request,user_id='demo-kusum').status_code == 404
    assert client.post(path,headers={'X-Demo-User-Id':request.requester_id}).status_code == 422
    user = get_user(request.requester_id)
    save_user(user.model_copy(update={'hard_constraints':user.hard_constraints.model_copy(update={'allowed_activities':['study']})}))
    class NeverCalled(MockAgentAdapter):
        async def negotiate(self,*args,**kwargs): pytest.fail('No model call when no candidates')
    app.dependency_overrides[get_agent_adapter] = lambda: NeverCalled()
    response = negotiate(client,request)
    assert response.status_code == 200 and response.json()['status']=='no_match'
    assert response.json()['proposal'] is None
    assert list_proposals_for_request(request.id) == []


def test_total_negotiation_timeout_is_bounded_and_saves_nothing(prepared,monkeypatch):
    import asyncio
    client, request = prepared
    class Slow(MockAgentAdapter):
        async def negotiate(self,*args,**kwargs):
            await asyncio.sleep(1)
            return await super().negotiate(*args,**kwargs)
    monkeypatch.setattr('backend.services.negotiation.NEGOTIATION_TIMEOUT_SECONDS',0.001)
    app.dependency_overrides[get_agent_adapter] = lambda: Slow()
    response = negotiate(client,request)
    assert response.status_code == 502
    assert list_proposals_for_request(request.id) == []


def test_saved_note_is_loaded_for_its_owner_on_next_negotiation(prepared):
    client, request = prepared
    note = 'PRIVATE_CHANGED_NOTE: prefer a short coffee.'
    result = client.patch('/users/me/preferences',headers={'X-Demo-User-Id':request.requester_id},json={'soft_preference_note':note})
    assert result.status_code == 200
    captured = []
    class Capture(MockAgentAdapter):
        async def negotiate(self, request, options, requester_ctx, invitee_ctx, **kwargs):
            captured.extend([requester_ctx,invitee_ctx])
            return await super().negotiate(request,options,requester_ctx,invitee_ctx,**kwargs)
    app.dependency_overrides[get_agent_adapter] = lambda: Capture()
    response = negotiate(client,request)
    assert response.status_code == 200
    assert captured[0].soft_preference_note == note
    assert captured[1].soft_preference_note != note
    assert note not in response.text


def test_exchange_history_survives_reload_for_both_participants_only(prepared):
    client, request = prepared
    path = f'/hangout-requests/{request.id}/negotiation'
    headers = {'X-Demo-User-Id': request.requester_id}
    assert client.get(path, headers=headers).json() is None
    first = negotiate(client, request).json()
    assert first['candidate_count'] > 0
    assert first['outcome_code'] is None
    for uid in (request.requester_id, request.invitee_id):
        response = client.get(path, headers={'X-Demo-User-Id': uid})
        assert response.status_code == 200
        assert response.json() == first
    assert client.get(path).status_code == 401
    assert client.get(path, headers={'X-Demo-User-Id': 'demo-kusum'}).status_code == 404
    # The latest exchange can differ from an earlier saved receipt.
    user = get_user(request.requester_id)
    save_user(user.model_copy(update={'hard_constraints': user.hard_constraints.model_copy(
        update={'allowed_activities': ['study']})}))
    second = negotiate(client, request, key='another-attempt').json()
    assert second['candidate_count'] == 0
    assert second['outcome_code'] == 'no_eligible_options'
    assert second['turns'] == []
    assert client.get(path, headers=headers).json() == second


def test_compacting_agent_options_preserves_only_authorized_combinations():
    from backend.models import CandidateOption
    from backend.services.agent_adapter import compact_options
    slot = {'start':'2026-10-23T14:00:00Z', 'end':'2026-10-23T16:00:00Z'}
    options = [CandidateOption(slot=slot, eligible_activities=[a], eligible_durations=d)
               for a,d in [('walk',[30,60]),('meal',[30,60]),('study',[30])]]
    compact = compact_options(options)
    assert len(compact) == 2
    def combinations(items):
        return {(o.slot.start,o.slot.end,a,d) for o in items for a in o.eligible_activities for d in o.eligible_durations}
    assert combinations(compact) == combinations(options)
    assert options[0].eligible_activities == ['walk']


def test_local_adapter_bounds_model_schema_to_eligible_choices(prepared, monkeypatch):
    from backend.models import CandidateOption
    from backend.services.agent_adapter import owner_context_from_user
    import asyncio
    _, request = prepared
    seen = []
    class Model:
        def chat(self, messages, **kwargs):
            properties = kwargs['format']['anyOf'][0]['properties']
            seen.append(properties)
            return json.dumps({'decision': 'propose' if len(seen)==1 else 'accept',
                               'option_index':0, 'activity':'walk', 'duration_minutes':30})
    monkeypatch.setattr('agent.negotiate.LocalLLM', Model)
    options = [CandidateOption(slot={'start': request.start, 'end': request.end},
                               eligible_activities=['walk'], eligible_durations=[30])]
    result = asyncio.run(LocalAgentAdapter(fallback_on_error=False).negotiate(
        request.model_copy(update={'allowed_activities':['walk']}), options,
        owner_context_from_user(get_user(request.requester_id)),
        owner_context_from_user(get_user(request.invitee_id))))
    assert result.status == 'agreed'
    assert len(seen) == 2
    for properties in seen:
        assert properties['activity']['enum'] == ['walk']
        assert properties['duration_minutes']['enum'] == [30]
        assert properties['option_index']['const'] == 0


def test_another_option_never_repeats_an_existing_plan_and_retries_replay(prepared):
    client, request = prepared
    first = negotiate(client, request).json()
    second = negotiate(client, request, key='another-option').json()
    def exact(result):
        return (result['proposal']['activity'], result['proposal']['slot'])
    assert first['status'] == second['status'] == 'agreed'
    assert exact(first) != exact(second)
    assert negotiate(client, request, key='another-option').json() == second
    assert len(list_proposals_for_request(request.id)) == 2


def test_alternative_search_exposes_later_starts_and_reports_exhaustion(prepared):
    from backend.models import CandidateOption, Proposal
    from backend.services.negotiation import unseen_options
    option = CandidateOption(slot={'start':'2026-10-23T14:00:00Z','end':'2026-10-23T15:00:00Z'},
                             eligible_activities=['walk'],eligible_durations=[30])
    first = Proposal(id='first',request_id='r',activity='walk',slot={
        'start':'2026-10-23T14:00:00Z','end':'2026-10-23T14:30:00Z'})
    choices = unseen_options([option], [first])
    assert len(choices) == 1
    assert choices[0].slot.start.isoformat() == '2026-10-23T14:30:00+00:00'
    second = first.model_copy(update={'id':'second','slot':choices[0].slot})
    assert unseen_options([option], [first,second]) == []


def test_invalid_model_combination_gets_one_corrective_retry(prepared, monkeypatch):
    from backend.models import CandidateOption
    from backend.services.agent_adapter import owner_context_from_user
    import asyncio
    _, request = prepared
    calls = []
    class Model:
        def chat(self, messages, **kwargs):
            calls.append(messages)
            if len(calls) == 1:
                return json.dumps({'decision':'propose','option_index':0,'activity':'coffee','duration_minutes':30})
            return json.dumps({'decision':'propose' if len(calls)==2 else 'accept',
                               'option_index':0,'activity':'walk','duration_minutes':30})
    monkeypatch.setattr('agent.negotiate.LocalLLM', Model)
    option = CandidateOption(slot={'start':request.start,'end':request.end},eligible_activities=['walk'],eligible_durations=[30])
    result = asyncio.run(LocalAgentAdapter(fallback_on_error=False).negotiate(
        request.model_copy(update={'allowed_activities':['walk']}), [option],
        owner_context_from_user(get_user(request.requester_id)),owner_context_from_user(get_user(request.invitee_id))))
    assert result.status == 'agreed' and len(calls) == 3
    assert 'valid combination' in calls[1][-1].content


def test_invalid_model_retry_is_bounded_and_failure_message_is_safe(prepared,monkeypatch):
    client, request = prepared
    calls = []
    class Model:
        def chat(self, messages, **kwargs):
            calls.append(1)
            return json.dumps({'decision':'propose','option_index':9999,'activity':'walk','duration_minutes':30,'reason':'PRIVATE_REASON'})
    monkeypatch.setattr('agent.negotiate.LocalLLM', Model)
    app.dependency_overrides[get_agent_adapter] = lambda: LocalAgentAdapter(fallback_on_error=False)
    response = negotiate(client,request)
    assert response.status_code == 502
    assert len(calls) == 2
    assert 'valid plan' in response.json()['detail']
    assert 'PRIVATE_REASON' not in response.text
    assert list_proposals_for_request(request.id) == []


def test_flat_schema_preserves_valid_no_match_without_forcing_a_plan(prepared, monkeypatch):
    client, request = prepared
    schemas = []
    class Model:
        def chat(self, messages, **kwargs):
            schemas.append(kwargs['format'])
            return json.dumps({'decision':'no_match','reason':'PRIVATE_VETO'})
    monkeypatch.setattr('agent.negotiate.LocalLLM', Model)
    app.dependency_overrides[get_agent_adapter] = lambda: LocalAgentAdapter(fallback_on_error=False)
    response = negotiate(client,request)
    assert response.status_code == 200
    assert response.json()['status'] == 'no_match'
    assert len(schemas) == 1
    assert 'PRIVATE_VETO' not in response.text
    variants = schemas[0]['anyOf']
    assert variants[-1]['properties']['decision']['const'] == 'no_match'
    for variant in variants[:-1]:
        assert 'option_index' in variant['required']
        assert 'const' in variant['properties']['option_index']
        assert variant['additionalProperties'] is False


def test_different_time_excludes_start_regardless_of_activity_or_duration(prepared):
    client, request = prepared
    first = negotiate(client, request).json()
    path = f'/hangout-requests/{request.id}/negotiate?variation=different_time'
    headers = {'X-Demo-User-Id':request.requester_id,'Idempotency-Key':'new-time'}
    response = client.post(path,headers=headers)
    assert response.status_code == 200, response.text
    second = response.json()
    assert second['status'] == 'agreed'
    assert second['proposal']['slot']['start'] != first['proposal']['slot']['start']
    assert client.post(path,headers=headers).json() == second
    # The same key cannot silently replay a different variation.
    assert client.post(path.split('?')[0],headers=headers).status_code == 409
    assert client.post(path.replace('different_time','unknown'),headers={**headers,'Idempotency-Key':'invalid-mode'}).status_code == 422


def test_different_time_no_remaining_start_skips_agents(prepared,monkeypatch):
    from backend.models import CandidateOption
    client, request = prepared
    first = negotiate(client,request).json()['proposal']
    only = CandidateOption(slot=first['slot'],eligible_activities=[first['activity']],eligible_durations=[30])
    async def candidates(*args): return [only]
    monkeypatch.setattr('backend.services.negotiation.build_candidates', candidates)
    class NeverCalled(MockAgentAdapter):
        async def negotiate(self,*args,**kwargs): pytest.fail('no new time must skip inference')
    app.dependency_overrides[get_agent_adapter] = lambda: NeverCalled()
    response = client.post(f'/hangout-requests/{request.id}/negotiate?variation=different_time',headers={
        'X-Demo-User-Id':request.requester_id,'Idempotency-Key':'no-new-time'})
    assert response.status_code == 200
    assert response.json()['outcome_code'] == 'no_new_options'
    assert len(list_proposals_for_request(request.id)) == 1
