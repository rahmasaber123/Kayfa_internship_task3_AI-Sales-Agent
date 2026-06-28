"""Persist and load chat turns."""
from datetime import datetime, timezone
from src.config import COL_MESSAGES
from src.memory.mongo import get_db

def save_turn(user_id: str, session_id: str, role: str, content: str, 
              language: str = "ar", tool_calls: list[dict] | None = None) -> None:
    """Write one chat turn, tagged with user_id."""
    get_db()[COL_MESSAGES].insert_one({
        "user_id": user_id, 
        "session_id": session_id,
        "role": role,
        "content": content,
        "language": language,
        "tool_calls": tool_calls or [],
        "timestamp": datetime.now(timezone.utc),
    })

def load_session_messages(session_id: str) -> list[dict]:
    """Return every turn for a session in chronological order."""
    return list(
        get_db()[COL_MESSAGES]
        .find({"session_id": session_id}, {"_id": 0})
        .sort("timestamp", 1)
    )
