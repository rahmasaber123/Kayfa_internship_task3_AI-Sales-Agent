"""Scan user text for competitor platform mentions."""
from src.config import COMPETITORS


def detect_competitor(text: str) -> str | None:
    """Return the first competitor name found in text (lowercased), else None."""
    low = text.lower()
    for c in COMPETITORS:
        if c in low:
            return c
    return None
