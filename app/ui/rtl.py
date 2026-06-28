"""Detect RTL/LTR direction per message based on script content."""
import re

_ARABIC_RE = re.compile(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]')


def detect_direction(text: str) -> str:
    """Return 'rtl' if text is predominantly Arabic, else 'ltr'."""
    if not text:
        return 'ltr'
    arabic_chars = len(_ARABIC_RE.findall(text))
    # 25% Arabic chars threshold — handles mixed messages naturally
    return 'rtl' if arabic_chars > max(2, len(text) * 0.25) else 'ltr'
