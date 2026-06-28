"""Output-side guardrails: check the agent's reply for fabricated prices against JSON."""
import re
import json
from pathlib import Path

PRICE_PATTERN = re.compile(r"\$(\d{1,4})\b")

def find_fabricated_prices(reply: str) -> list[int]:
    """Return prices mentioned in reply that DON'T exist in the JSON catalog.
    Empty list = all good (or no prices mentioned)."""
    mentioned = {int(m) for m in PRICE_PATTERN.findall(reply)}
    if not mentioned:
        return []
    
    # Load known prices directly from the JSON Truth Source
    catalog_path = Path("src/kb/catalog.json")
    if not catalog_path.exists():
        return [] # Skip validation if file is missing
        
    with open(catalog_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    known = set()
    for track in data.get("educational_tracks", []):
        if "price_usd" in track: known.add(track["price_usd"])
    for course in data.get("individual_courses", []):
        if "price_usd" in course: known.add(course["price_usd"])

    # Allow $0 (free) always
    fabricated = sorted(p for p in mentioned if p != 0 and p not in known)
    return fabricated

def validate_reply(reply: str) -> list[str]:
    """Return list of issues found. Empty = passed."""
    issues = []
    fab = find_fabricated_prices(reply)
    if fab:
        issues.append(f"fabricated prices: {fab}")
    return issues
