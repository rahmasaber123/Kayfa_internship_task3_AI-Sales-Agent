"""Live working profile of the visitor — updated by the agent each turn."""
from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field

from src.config import COL_PROFILES
from src.memory.mongo import get_db


Temperature = Literal["cold", "warm", "hot"]


class UserProfile(BaseModel):
    """The agent's live model of who it's talking to. Becomes the lead ticket draft."""
    session_id: str
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    city: str | None = None
    country: str | None = None
    language: str = "ar"
    dialect: str | None = None
    products_mentioned: list[str] = Field(default_factory=list)
    goal: str | None = None
    current_level: str | None = None
    buying_signals: list[str] = Field(default_factory=list)
    objections_raised: list[str] = Field(default_factory=list)

    # Set when escalate_to_human fires — used to prevent double-escalation.
    escalation_ticket_id: str | None = None
    lead_ticket_id: str | None = None
    temperature: Temperature = "cold"
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


def get_profile(session_id: str) -> UserProfile:
    """Fetch profile from Mongo. Returns a fresh one if missing."""
    doc = get_db()[COL_PROFILES].find_one({"session_id": session_id}, {"_id": 0})
    if not doc:
        return UserProfile(session_id=session_id)
    return UserProfile.model_validate(doc)


def save_profile(profile: UserProfile) -> None:
    profile.updated_at = datetime.now(timezone.utc)
    get_db()[COL_PROFILES].replace_one(
        {"session_id": profile.session_id},
        profile.model_dump(mode="json"),
        upsert=True,
    )


def apply_updates(profile: UserProfile, updates: dict) -> UserProfile:
    """Apply a partial dict (from the agent's tool call) onto the profile.
    Lists are extended (dedup); scalars are overwritten if non-empty."""
    LIST_FIELDS = {"products_mentioned", "buying_signals", "objections_raised"}
    for k, v in updates.items():
        if v in (None, "", []):
            continue
        if k in LIST_FIELDS and isinstance(v, list):
            current = set(getattr(profile, k, []))
            current.update(v)
            setattr(profile, k, sorted(current))
        elif hasattr(profile, k):
            setattr(profile, k, v)
    return profile
