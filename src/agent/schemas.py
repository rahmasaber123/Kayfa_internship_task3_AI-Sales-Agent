"""Structured output schema for every agent turn."""
from typing import Literal
from pydantic import BaseModel, Field


Temperature = Literal["cold", "warm", "hot"]


class ProfileDelta(BaseModel):
    """Partial updates to the user profile that the agent learned this turn."""
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    city: str | None = None
    country: str | None = None
    goal: str | None = None
    current_level: str | None = None
    products_mentioned: list[str] = Field(default_factory=list)
    buying_signals: list[str] = Field(default_factory=list)
    objections_raised: list[str] = Field(default_factory=list)


class AgentReply(BaseModel):
    """What the agent returns on every turn."""
    reply: str = Field(description="The message to show the user, in their language/dialect")
    temperature: Temperature = Field(
        default="cold",
        description="Lead temperature after this turn",
    )
    profile_delta: ProfileDelta = Field(
        default_factory=ProfileDelta,
        description="Profile fields you learned or inferred this turn",
    )
