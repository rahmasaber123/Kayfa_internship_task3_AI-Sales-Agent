"""Rolling conversation summary — compresses old turns to keep context bounded.

Wiring is left for v1.5: the function works; we just don't call it during the
first 6-turn demo conversations (none reach the trigger). Day 2 wires it into
the main turn handler when sessions go long.
"""
from datetime import datetime, timezone
from pydantic_ai import Agent

from src.config import SUMMARIZER_MODEL, SUMMARY_TRIGGER_TURNS, SUMMARY_KEEP_RECENT, COL_SUMMARIES
from src.memory.mongo import get_db
from src.prompts import load


_summarizer: Agent | None = None


def _get_summarizer() -> Agent:
    """Build (once) a small fast agent dedicated to compression."""
    global _summarizer
    if _summarizer is None:
        _summarizer = Agent(
            SUMMARIZER_MODEL,
            instructions=load("system/summarizer"),
        )
    return _summarizer


def _format_history(turns: list[dict]) -> str:
    lines = []
    for t in turns:
        role = t.get("role", "user").upper()
        lines.append(f"[{role}] {t.get('content', '')}")
    return "\n".join(lines)


async def summarize_old_turns(session_id: str, history: list[dict]) -> list[dict] | None:
    """If history has more than SUMMARY_TRIGGER_TURNS, compress everything except
    the last SUMMARY_KEEP_RECENT turns. Returns the new compressed history, or
    None if no compression was needed.
    """
    if len(history) < SUMMARY_TRIGGER_TURNS:
        return None

    old = history[:-SUMMARY_KEEP_RECENT]
    recent = history[-SUMMARY_KEEP_RECENT:]

    summarizer = _get_summarizer()
    result = await summarizer.run(_format_history(old))
    summary_text = str(result.output)

    get_db()[COL_SUMMARIES].insert_one({
        "session_id": session_id,
        "created_at": datetime.now(timezone.utc),
        "turn_range": [0, len(old) - 1],
        "summary": summary_text,
    })

    return [
        {"role": "system", "content": f"Conversation so far: {summary_text}"},
        *recent,
    ]
