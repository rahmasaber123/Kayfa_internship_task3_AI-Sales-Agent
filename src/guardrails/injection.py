"""Detect prompt-injection attempts. Returns a list of matched patterns (empty = clean)."""
import re

INJECTION_PATTERNS = [
    r"ignore (all |the )?(previous|prior|above) (instructions|prompts?|rules?)",
    r"forget (everything|all|your) (instructions|rules|prompt)",
    r"you are now",
    r"new instructions:",
    r"system prompt",
    r"reveal (your|the) (system|prompt|instructions)",
    r"act as",
    r"pretend (to be|you are)",
    r"jailbreak",
    r"DAN mode",
    # Arabic variants
    r"تجاهل (كل|جميع)? ?التعليمات",
    r"انس (ال)?تعليمات",
    r"انت الان",
    r"اظهر (ال)?برومبت",
]

_COMPILED = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]


def detect_injection(text: str) -> list[str]:
    """Return list of matched pattern strings (empty if no injection detected)."""
    matches = []
    for pat in _COMPILED:
        if pat.search(text):
            matches.append(pat.pattern)
    return matches
