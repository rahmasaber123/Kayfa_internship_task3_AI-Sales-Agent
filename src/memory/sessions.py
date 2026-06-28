"""Session lifecycle: create, update, fetch."""
from datetime import datetime, timezone
from uuid import uuid4
from src.config import COL_SESSIONS
from src.memory.mongo import get_db


def create_session(language: str = "ar", dialect: str | None = None) -> str:
    """Create a new session and return its session_id."""
    sid = str(uuid4())
    now = datetime.now(timezone.utc)
    get_db()[COL_SESSIONS].insert_one({
        "session_id": sid,
        "created_at": now,
        "last_active_at": now,
        "language": language,
        "dialect": dialect,
        "status": "active",
        "turn_count": 0,
        "lead_id": None,
    })
    return sid


def touch_session(session_id: str, language: str | None = None,
                  dialect: str | None = None) -> None:
    """Update last_active_at + bump turn count + optionally update language/dialect."""
    update = {
        "$set": {"last_active_at": datetime.now(timezone.utc)},
        "$inc": {"turn_count": 1},
    }
    if language:
        update["$set"]["language"] = language
    if dialect:
        update["$set"]["dialect"] = dialect
    get_db()[COL_SESSIONS].update_one({"session_id": session_id}, update, upsert=False)


def get_session(session_id: str) -> dict | None:
    return get_db()[COL_SESSIONS].find_one({"session_id": session_id}, {"_id": 0})


def mark_session_status(session_id: str, status: str, lead_id: str | None = None) -> None:
    upd = {"$set": {"status": status}}
    if lead_id is not None:
        upd["$set"]["lead_id"] = lead_id
    get_db()[COL_SESSIONS].update_one({"session_id": session_id}, upd)
def delete_session(session_id: str) -> dict:
    """Delete a session and ALL its associated data (messages, profile, summary).
    
    Returns counts of what was deleted. Tickets are preserved — they're owned
    by the sales team, not the visitor.
    """
    from src.memory.mongo import get_db
    from src.config import (
        COL_SESSIONS, COL_MESSAGES, COL_PROFILES, COL_SUMMARIES  # ← التعديل هنا
    )
    db = get_db()
    result = {
        "messages":  db[COL_MESSAGES].delete_many({"session_id": session_id}).deleted_count,
        "profile":   db[COL_PROFILES].delete_many({"session_id": session_id}).deleted_count, # ← والتعديل هنا
        "summary":   db[COL_SUMMARIES].delete_many({"session_id": session_id}).deleted_count,
        "session":   db[COL_SESSIONS].delete_many({"session_id": session_id}).deleted_count,
    }
    return result


def delete_all_sessions() -> dict:
    """Wipe ALL chat data — sessions, messages, profiles, summaries.
    Tickets preserved. Returns counts."""
    from src.memory.mongo import get_db
    from src.config import (
        COL_SESSIONS, COL_MESSAGES, COL_PROFILES, COL_SUMMARIES  # ← التعديل هنا
    )
    db = get_db()
    return {
        "messages":  db[COL_MESSAGES].delete_many({}).deleted_count,
        "profile":   db[COL_PROFILES].delete_many({}).deleted_count, # ← والتعديل هنا
        "summary":   db[COL_SUMMARIES].delete_many({}).deleted_count,
        "session":   db[COL_SESSIONS].delete_many({}).deleted_count,
    }
