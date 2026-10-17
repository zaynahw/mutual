"""Backend-owned validation; all timestamps must include UTC offsets."""
from typing import Literal
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")

class Interval(Model):
    start: AwareDatetime
    end: AwareDatetime

    @model_validator(mode="after")
    def ordered(self):
        if self.end <= self.start:
            raise ValueError("end must be after start")
        return self

class User(Model):
    id: str = Field(pattern=r"^demo-[a-z0-9-]+$")
    display_name: str = Field(min_length=1)
    is_demo: Literal[True] = True
    timezone: str = "UTC"  # Display hint; interval offsets remain authoritative.
    availability_visible_to: list[str] = Field(default_factory=list)
    activity_preferences: list[str] = Field(default_factory=list)
    boundaries: list[str] = Field(default_factory=list)

class SocialWindow(Interval):
    user_id: str

class BusyInterval(Interval):
    user_id: str

class HangoutRequest(Interval):
    id: str
    requester_id: str
    invitee_id: str
    activity: str = Field(min_length=1)
    duration_minutes: int = Field(gt=0, le=1440)

    @model_validator(mode="after")
    def distinct_users(self):
        if self.requester_id == self.invitee_id:
            raise ValueError("participants must be different")
        if (self.end - self.start).total_seconds() < self.duration_minutes * 60:
            raise ValueError("request range is shorter than duration")
        return self

class CandidateSlot(Interval):
    pass

class Proposal(Model):
    id: str
    request_id: str
    slot: CandidateSlot
    status: Literal["pending", "approved", "declined", "scheduled"] = "pending"

class Approval(Model):
    proposal_id: str
    user_id: str
    decision: Literal["approve", "decline"]
    decided_at: AwareDatetime
