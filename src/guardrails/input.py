"""Input-side guardrails: length, emptiness, basic sanity."""
from src.config import MAX_USER_MESSAGE_CHARS


class InputRejected(Exception):
    pass


def validate_input(text: str) -> str:
    """Return cleaned text or raise InputRejected."""
    if text is None:
        raise InputRejected("empty message")
    stripped = text.strip()
    if not stripped:
        raise InputRejected("empty message")
    if len(stripped) > MAX_USER_MESSAGE_CHARS:
        raise InputRejected(f"message too long (>{MAX_USER_MESSAGE_CHARS} chars)")
    return stripped
