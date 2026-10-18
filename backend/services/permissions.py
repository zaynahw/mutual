"""Audience eligibility only; callers separately filter fields and sharing mode.

Pass trusted users loaded by the backend, not identities supplied in a body.
This helper is shared by future calendar browsing and social-window services.
"""
from backend.friendships import are_friends
from backend.models import User, VisibilityPolicy


def can_access(owner: User, viewer: User, policy: VisibilityPolicy) -> bool:
    """Evaluate a policy using current friendship state, without caching grants."""
    if owner.id == viewer.id:
        return True
    if policy.audience == "private":
        return False
    if policy.audience == "community":
        return owner.community is not None and owner.community == viewer.community
    if policy.audience == "friends":
        return are_friends(owner.id, viewer.id)
    if policy.audience == "selected_friends":
        return (
            viewer.id in policy.selected_friend_ids
            and are_friends(owner.id, viewer.id)
        )
    return False


def validate_selected_friends(owner: User, policy: VisibilityPolicy) -> None:
    """Validate selected audience relationships; Pydantic checks list structure."""
    if policy.audience != "selected_friends":
        return
    for friend_id in policy.selected_friend_ids:
        if friend_id == owner.id:
            raise ValueError("Cannot select yourself as a friend")
        if not are_friends(owner.id, friend_id):
            raise ValueError("Selected users must be accepted friends")
