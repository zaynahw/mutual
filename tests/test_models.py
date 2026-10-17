"""Record validation and contract consistency; authorization routes are future work."""
import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from backend.models import (
    Approval, CandidateOption, FriendRequest, HangoutRequestCreate,
    HardConstraints, ProposalCreate, PublicUser, ScheduleResponse,
    SocialWindowCreate, User, UserSettings, VisibilityPolicy,
)
from backend.scripts.export_schemas import schemas


def example_data():
    return json.loads(Path('contracts/examples.json').read_text())


def test_all_additional_examples():
    data = example_data()
    for key, model in [('friend_requests', FriendRequest), ('candidate_options', CandidateOption), ('approvals', Approval)]:
        for value in data[key]:
            model.model_validate(value)
    front = data['frontend_examples']
    HangoutRequestCreate.model_validate(front['create_request'])
    for key in ('schedule_for_daniella', 'schedule_for_kusum'):
        ScheduleResponse.model_validate(front[key])
    assert front['schedule_for_kusum']['calendar_busy'] is None
    assert front['schedule_for_daniella']['calendar_busy']


@pytest.mark.parametrize('payload', [
    {'audience': 'selected_friends'},
    {'audience': 'friends', 'selected_friend_ids': ['demo-daniella']},
    {'audience': 'selected_friends', 'selected_friend_ids': ['demo-daniella', 'demo-daniella']},
])
def test_visibility_configuration(payload):
    with pytest.raises(ValidationError):
        VisibilityPolicy.model_validate(payload)


def test_calendar_default_is_private_and_public_projection_excludes_secrets():
    raw = example_data()['users'][1]
    raw.pop('calendar_sharing')
    user = User.model_validate(raw)
    assert user.calendar_sharing.audience == 'private'
    public = PublicUser.model_validate({name: getattr(user, name) for name in PublicUser.model_fields})
    assert set(public.model_dump()) == {'id', 'display_name', 'community', 'is_demo'}
    with pytest.raises(ValidationError):
        PublicUser.model_validate(user.model_dump())


@pytest.mark.parametrize('duration', [True, 45, 150, '60'])
def test_supported_durations_are_strict(duration):
    with pytest.raises(ValidationError):
        HardConstraints(allowed_activities=['coffee'], max_duration_minutes=duration)


def test_request_input_rejects_server_owned_fields():
    raw = example_data()['request']
    with pytest.raises(ValidationError):
        HangoutRequestCreate.model_validate(raw)


@pytest.mark.parametrize('changes', [
    {'allowed_activities': ['coffee', 'coffee']},
    {'allowed_durations': [30, 30]},
    {'allowed_activities': ['dinner']},
    {'end': '2026-10-18T14:15:00-04:00'},
])
def test_invalid_search_choices(changes):
    raw = example_data()['frontend_examples']['create_request']
    with pytest.raises(ValidationError):
        HangoutRequestCreate.model_validate(raw | changes)


def test_friend_request_states():
    raw = example_data()['friend_requests'][1]
    for changes in ({'recipient_id': raw['sender_id']}, {'status': 'accepted'},
                    {'responded_at': raw['created_at']}):
        with pytest.raises(ValidationError):
            FriendRequest.model_validate(raw | changes)


def test_candidate_duration_and_proposal_validation():
    raw = example_data()['candidate_options'][0]
    with pytest.raises(ValidationError):
        CandidateOption.model_validate(raw | {'eligible_durations': [120]})
    slot = raw['slot'] | {'end': '2026-10-18T15:45:00-04:00'}
    with pytest.raises(ValidationError):
        ProposalCreate(activity='coffee', slot=slot)


def test_timezone_and_one_time_windows():
    raw = example_data()['users'][0]
    with pytest.raises(ValidationError):
        User.model_validate(raw | {'timezone': 'Mars/Olympus'})
    window = example_data()['social_windows'][0]
    window = {k:v for k,v in window.items() if k not in ('id', 'user_id')}
    with pytest.raises(ValidationError):
        SocialWindowCreate.model_validate(window | {'recurrence': 'weekly'})
    settings = {k:raw[k] for k in UserSettings.model_fields}
    with pytest.raises(ValidationError):
        UserSettings.model_validate(settings | {'community': 'georgia_tech'})


def test_generated_schemas_are_current():
    assert json.loads(Path('contracts/schemas.json').read_text()) == schemas()
