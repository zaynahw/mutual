"""Exercise audience rules against actual SQLite friendship state."""
import pytest

from backend.friendships import (
    create_friend_request, remove_friendship, respond_to_friend_request,
)
from backend.models import VisibilityPolicy
from backend.repositories import get_user
from backend.seed import seed_demo_data
from backend.services.permissions import can_access


@pytest.fixture
def people(tmp_path, monkeypatch):
    monkeypatch.setenv('MUTUAL_DATABASE_PATH', str(tmp_path / 'permissions.db'))
    seed_demo_data()
    return get_user('demo-zaynah'), get_user('demo-daniella'), get_user('demo-kusum')


def policy(audience, selected=None):
    return VisibilityPolicy(audience=audience, selected_friend_ids=selected or [])


@pytest.mark.parametrize('audience', ['private', 'community', 'friends', 'selected_friends'])
def test_owner_can_access_own_data(people, audience):
    owner, viewer, _ = people
    selected = [viewer.id] if audience == 'selected_friends' else []
    assert can_access(owner, owner, policy(audience, selected)) is True


def test_private_is_not_granted_even_to_accepted_friend(people):
    owner, viewer, _ = people
    request = create_friend_request(owner.id, viewer.id)
    respond_to_friend_request(request.id, viewer.id, 'accept')
    assert can_access(owner, viewer, policy('private')) is False


def test_community_does_not_require_friendship(people):
    owner, viewer, _ = people
    assert can_access(owner, viewer, policy('community')) is True


@pytest.mark.parametrize('reverse', [False, True])
@pytest.mark.parametrize('audience', ['friends', 'selected_friends'])
def test_acceptance_grants_access_removal_revokes_it_and_reacceptance_restores_it(people, reverse, audience):
    owner, viewer, _ = people
    visibility = policy(audience, [viewer.id] if audience == 'selected_friends' else [])
    assert can_access(owner, viewer, visibility) is False
    sender, recipient = (viewer, owner) if reverse else (owner, viewer)
    request = create_friend_request(sender.id, recipient.id)
    assert can_access(owner, viewer, visibility) is False
    respond_to_friend_request(request.id, recipient.id, 'accept')
    assert can_access(owner, viewer, visibility) is True
    remove_friendship(request.id, sender.id)
    assert can_access(owner, viewer, visibility) is False
    assert can_access(owner, viewer, policy('community')) is True
    newer = create_friend_request(sender.id, recipient.id)
    respond_to_friend_request(newer.id, recipient.id, 'accept')
    assert can_access(owner, viewer, visibility) is True


def test_selected_friends_requires_selection_as_well_as_friendship(people):
    owner, viewer, other = people
    for person in (viewer, other):
        request = create_friend_request(owner.id, person.id)
        respond_to_friend_request(request.id, person.id, 'accept')
    visibility = policy('selected_friends', [viewer.id])
    assert can_access(owner, viewer, visibility) is True
    assert can_access(owner, other, visibility) is False


@pytest.mark.parametrize('audience', ['friends', 'selected_friends'])
def test_declined_request_does_not_grant_access(people, audience):
    owner, viewer, _ = people
    request = create_friend_request(owner.id, viewer.id)
    respond_to_friend_request(request.id, viewer.id, 'decline')
    visibility = policy(audience, [viewer.id] if audience == 'selected_friends' else [])
    assert can_access(owner, viewer, visibility) is False
