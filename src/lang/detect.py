"""Detect language (ar/en) + Arabic dialect via simple markers."""
from langdetect import detect as _ld_detect, DetectorFactory, LangDetectException

DetectorFactory.seed = 42  # deterministic

# Dialect markers (lowercased substrings)
EGYPTIAN_MARKERS = ["ايه", "إيه", "ازاي", "إزاي", "كده", "عايز", "يلا", "ابعت", "بقى", "احنا", "انت", "دي", "ده "]
SAUDI_MARKERS    = ["وش", "ايش", "إيش", "الحين", "تبي", "ابي", "ابغى", "كذا", "زين"]
SYRIAN_MARKERS   = ["شو", "هلق", "كتير", "بدي", "كيفك", "هاد", "هون", "منيح"]
UAE_MARKERS      = ["هيه", "انزين", "شحالك", "حيّاك", "ريال", "ملا", "خلاص", "أبشر"]


def detect_language(text: str) -> str:
    """Return 'ar' or 'en' (fallback 'en' on error or empty)."""
    if not text or not text.strip():
        return "en"
    # Quick check: if string contains Arabic letters, treat as Arabic.
    if any("\u0600" <= ch <= "\u06ff" for ch in text):
        return "ar"
    try:
        code = _ld_detect(text)
    except LangDetectException:
        return "en"
    return "ar" if code == "ar" else "en"


def detect_dialect(text: str, lang: str | None = None) -> str | None:
    """Return one of: 'egyptian' | 'saudi' | 'syrian' | 'uae' | 'msa' | None."""
    if lang is None:
        lang = detect_language(text)
    if lang != "ar":
        return None

    low = text.lower()
    scores = {
        "egyptian": sum(1 for m in EGYPTIAN_MARKERS if m in low),
        "saudi":    sum(1 for m in SAUDI_MARKERS    if m in low),
        "syrian":   sum(1 for m in SYRIAN_MARKERS   if m in low),
        "uae":      sum(1 for m in UAE_MARKERS      if m in low),
    }
    # Get best dialect, defaulting to msa if no dialect markers found
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "msa"


def detect(text: str) -> tuple[str, str | None]:
    """Convenience: returns (language, dialect)."""
    lang = detect_language(text)
    return lang, detect_dialect(text, lang)
