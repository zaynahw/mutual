"""Shared domain and API schemas. Authorization belongs in backend services."""
from datetime import date, timezone
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

Activity = Literal["coffee", "meal", "walk", "study", "concert"]
DurationMinutes = Annotated[int, Field(strict=True, ge=30, le=120, multiple_of=30)]
UserId = Annotated[str, Field(pattern=r"^(?:demo-[a-z0-9-]+|user-[a-f0-9]{32})$")]
# Compatibility name for agent-lane imports; new code should use UserId.
DemoUserId = UserId
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


class PreferenceNoteUpdate(Model):
    soft_preference_note: str = Field(max_length=1000)


class HardConstraints(Model):
    allowed_activities: list[Activity] = Field(min_length=1)
    max_duration_minutes: DurationMinutes = 120


class MatchingSettings(Model):
    mode: Literal["social_windows", "calendar_guided"] = "social_windows"
    start_hour: Annotated[int, Field(strict=True, ge=0, le=23)] = 9
    end_hour: Annotated[int, Field(strict=True, ge=1, le=24)] = 21

    @model_validator(mode="after")
    def daytime_range(self):
        if self.end_hour <= self.start_hour:
            raise ValueError("End hour must be after start hour; overnight hours are not supported")
        return self


class UserSettings(Model):
    matching: MatchingSettings = Field(default_factory=MatchingSettings)
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
    is_demo: bool = True
    community: Literal["georgia_tech"] | None = "georgia_tech"


class PublicUser(Model):
    id: DemoUserId
    display_name: str
    is_demo: bool = True
    community: Literal["georgia_tech"] | None = "georgia_tech"


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
    search_windows: list[Interval] = Field(default_factory=list, max_length=7)
    invitee_id: DemoUserId
    allowed_activities: list[Activity] = Field(min_length=1)
    allowed_durations: list[DurationMinutes] = Field(min_length=1)
    location: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def duration_fits(self):
        if min(self.allowed_durations) > self.duration_minutes:
            raise ValueError("Search range cannot fit any allowed duration")
        previous_end = None
        for window in self.search_windows:
            if window.start < self.start or window.end > self.end:
                raise ValueError("Selected-day windows must fit within the search range")
            if previous_end is not None and window.start < previous_end:
                raise ValueError("Selected-day windows must be sorted and non-overlapping")
            previous_end = window.end
        return self


class HangoutRequest(HangoutRequestCreate):
    origin: Literal["manual", "intent"] = "manual"
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
    source: Literal["manual", "local_agent", "demo_fallback", "mock"] = "manual"
    id: str
    request_id: str
    location: str | None = Field(default=None, max_length=200)
    status: Literal["pending", "approved", "declined", "cancelled", "scheduled"] = "pending"


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


class HangoutOverview(Model):
    request: HangoutRequest
    proposals: list[ProposalResponse]


class PublicNegotiationTurn(Model):
    actor_id: DemoUserId
    decision: Literal["propose", "counter", "accept", "no_match"]
    activity: Activity | None = None
    slot: CandidateSlot | None = None


class NegotiationResponse(Model):
    status: Literal["agreed", "no_match", "exhausted"]
    source: Literal["local_agent", "demo_fallback", "mock"]
    proposal: Proposal | None = None
    turns: list[PublicNegotiationTurn] = Field(default_factory=list)


TimePeriod = Literal["morning", "afternoon", "evening"]
ClockTime = Annotated[str, Field(pattern=r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")]


class HangoutIntentCreate(Model):
    invitee_id: DemoUserId
    days: list[date] = Field(min_length=1, max_length=7)
    message: str = Field(min_length=1, max_length=1000)

    @field_validator("days")
    @classmethod
    def distinct_days(cls, value):
        if len(value) != len(set(value)):
            raise ValueError("Choose distinct dates")
        return sorted(value)

    @field_validator("message")
    @classmethod
    def nonblank_message(cls, value):
        if not value.strip():
            raise ValueError("Describe what you would like to do")
        return value.strip()


class IntentInterpretation(Model):
    activities: list[Activity] = Field(min_length=1, max_length=5)
    allowed_durations: list[DurationMinutes] = Field(min_length=1, max_length=4)
    preferred_periods: list[TimePeriod] = Field(default_factory=list, max_length=3)
    earliest: ClockTime | None = None
    latest: ClockTime | None = None
    clarification: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def consistent_choices(self):
        for values in (self.activities, self.preferred_periods):
            if len(values) != len(set(values)):
                raise ValueError("Interpretation choices must be unique")
        if self.earliest and self.latest and self.earliest >= self.latest and not self.clarification:
            raise ValueError("Conflicting time limits need clarification")
        return self


class IntentInterpretationResult(Model):
    source: Literal["local_agent", "demo_fallback", "mock"]
    interpretation: IntentInterpretation


class HangoutIntentDraft(Model):
    id: str
    owner_id: DemoUserId
    input: HangoutIntentCreate
    timezone: str
    result: IntentInterpretationResult
    request_id: str | None = None


class AuthStart(Model):
    purpose: Literal['login','calendar']='login'
    timezone: str='America/New_York'


class AuthStatus(Model):
    mode: Literal['demo','google']
    configured: bool
    authenticated: bool
    user: User | None
    calendar_mode: Literal['mock','google']
    calendar_connected: bool
