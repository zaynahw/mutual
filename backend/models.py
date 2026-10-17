"""Shared domain and API schemas. Authorization belongs in backend services."""
from datetime import timezone
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

Activity = Literal["coffee", "meal", "walk", "study", "concert"]
DurationMinutes = Annotated[int, Field(strict=True, ge=30, le=120, multiple_of=30)]
DemoUserId = Annotated[str, Field(pattern=r"^demo-[a-z0-9-]+$")]
Audience = Literal["private", "community", "friends", "selected_friends"]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def unique_choices(self):
        for field in ("selected_friend_ids", "preferred_activities", "allowed_activities",
                      "allowed_durations", "eligible_activities", "eligible_durations"):
            values = getattr(self, field, None)
            if values is not None and len(values) != len(set(values)):
                raise ValueError(f"{field} must contain unique values")
        return self


class Interval(Model):
    start: AwareDatetime
    end: AwareDatetime

    @model_validator(mode="after")
    def ordered(self):
        if self.end.astimezone(timezone.utc) <= self.start.astimezone(timezone.utc):
            raise ValueError("end must be after start")
        return self

    @property
    def duration_minutes(self) -> float:
        return (self.end.astimezone(timezone.utc) - self.start.astimezone(timezone.utc)).total_seconds() / 60


class VisibilityPolicy(Model):
    audience: Audience = "private"
    selected_friend_ids: list[DemoUserId] = Field(default_factory=list)

    @model_validator(mode="after")
    def selected_friends(self):
        if (self.audience == "selected_friends") != bool(self.selected_friend_ids):
            raise ValueError("Only selected_friends requires a nonempty selected_friend_ids list")
        return self


class Preferences(Model):
    preferred_activities: list[Activity] = Field(default_factory=list)
    soft_preference_note: str = Field(default="", max_length=1000)


class HardConstraints(Model):
    allowed_activities: list[Activity] = Field(min_length=1)
    max_duration_minutes: DurationMinutes = 120


class UserSettings(Model):
    timezone: str = "America/New_York"
    calendar_sharing: VisibilityPolicy = Field(default_factory=VisibilityPolicy)
    preferences: Preferences = Field(default_factory=Preferences)
    hard_constraints: HardConstraints

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Unknown IANA timezone")
        return value


class User(UserSettings):
    """Private owner record; never use as another user's profile response."""
    id: DemoUserId
    display_name: str = Field(min_length=1, max_length=100)
    is_demo: Literal[True] = True
    community: Literal["georgia_tech"] = "georgia_tech"


class PublicUser(Model):
    id: DemoUserId
    display_name: str
    is_demo: Literal[True] = True
    community: Literal["georgia_tech"] = "georgia_tech"


class FriendRequestCreate(Model):
    recipient_id: DemoUserId


class FriendRequestRespond(Model):
    decision: Literal["accept", "decline"]


class FriendRequest(Model):
    id: str
    sender_id: DemoUserId
    recipient_id: DemoUserId
    status: Literal["pending", "accepted", "declined", "removed"] = "pending"
    created_at: AwareDatetime
    responded_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def valid_state(self):
        if self.sender_id == self.recipient_id:
            raise ValueError("Cannot send yourself a friend request")
        if self.status == "pending" and self.responded_at is not None:
            raise ValueError("Pending request cannot have a response time")
        if self.status != "pending" and self.responded_at is None:
            raise ValueError("Answered request requires a response time")
        if self.responded_at is not None and self.responded_at < self.created_at:
            raise ValueError("Response cannot precede request")
        return self


class SocialWindowCreate(Interval):
    allowed_activities: list[Activity] = Field(min_length=1)
    visibility: VisibilityPolicy = Field(default_factory=VisibilityPolicy)
    sharing_mode: Literal["visible", "matching_only"] = "visible"


class SocialWindow(SocialWindowCreate):
    id: str
    user_id: DemoUserId


class SharedSocialWindow(Interval):
    """Viewer projection; excludes audience lists and matching-only windows."""
    id: str
    allowed_activities: list[Activity] = Field(min_length=1)


class BusyInterval(Interval):
    user_id: DemoUserId


class ScheduleResponse(Model):
    user: PublicUser
    social_windows: list[SharedSocialWindow]
    calendar_busy: list[Interval] | None = None  # null = not shared; [] = shared, no conflicts


class HangoutRequestCreate(Interval):
    invitee_id: DemoUserId
    allowed_activities: list[Activity] = Field(min_length=1)
    allowed_durations: list[DurationMinutes] = Field(min_length=1)
    location: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def duration_fits(self):
        if min(self.allowed_durations) > self.duration_minutes:
            raise ValueError("Search range cannot fit any allowed duration")
        return self


class HangoutRequest(HangoutRequestCreate):
    id: str
    requester_id: DemoUserId

    @model_validator(mode="after")
    def distinct_users(self):
        if self.requester_id == self.invitee_id:
            raise ValueError("Participants must be different")
        return self


class CandidateSlot(Interval):
    """Pure interval returned by deterministic intersection."""


class CandidateOption(Model):
    slot: CandidateSlot
    eligible_activities: list[Activity] = Field(min_length=1)
    eligible_durations: list[DurationMinutes] = Field(min_length=1)

    @model_validator(mode="after")
    def durations_fit(self):
        if max(self.eligible_durations) > self.slot.duration_minutes:
            raise ValueError("Eligible durations must fit the slot")
        return self


class ProposalCreate(Model):
    activity: Activity
    slot: CandidateSlot

    @model_validator(mode="after")
    def supported_duration(self):
        if self.slot.duration_minutes not in (30, 60, 90, 120):
            raise ValueError("Unsupported proposal duration")
        return self


class Proposal(ProposalCreate):
    id: str
    request_id: str
    location: str | None = Field(default=None, max_length=200)
    status: Literal["pending", "approved", "declined", "scheduled"] = "pending"


class ApprovalCreate(Model):
    decision: Literal["approve", "decline"]


class Approval(ApprovalCreate):
    proposal_id: str
    user_id: DemoUserId
    decided_at: AwareDatetime


class ProposalResponse(Model):
    proposal: Proposal
    approvals: list[Approval]


class CalendarEventResponse(Model):
    proposal_id: str
    event_id: str
