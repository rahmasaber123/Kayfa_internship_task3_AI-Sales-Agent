"""Per-turn dynamic context injection."""
from datetime import datetime
from pydantic_ai import RunContext
from src.agent.deps import AgentDeps


async def runtime_context(ctx: RunContext[AgentDeps]) -> str:
    """Built fresh on every agent.run() call. Injects live profile + flags."""
    p = ctx.deps.profile
    lines = [
        "## Current conversation context",
        f"- Language to reply in: **{ctx.deps.language}**",
        f"- Dialect: {ctx.deps.dialect or 'unknown'}",
        f"- Session id: {ctx.deps.session_id}",
        "",
        "## What I know about this user so far",
        f"- Name: {p.name or '(not given yet)'}",
        f"- Phone: {'(captured)' if p.phone else '(not given yet)'}",
        f"- City/Country: {p.city or '—'} / {p.country or '—'}",
        f"- Goal: {p.goal or '(unknown)'}",
        f"- Current level: {p.current_level or '(unknown)'}",
        f"- Products mentioned: {', '.join(p.products_mentioned) or 'none'}",
        f"- Buying signals: {', '.join(p.buying_signals) or 'none'}",
        f"- Objections raised: {', '.join(p.objections_raised) or 'none'}",
        f"- Lead temperature: **{p.temperature}**",
    ]
    if ctx.deps.competitor_flag:
        lines += [
            "",
            f"## ⚠ Competitor detected this turn: **{ctx.deps.competitor_flag}**",
            "→ Call `handle_competitor_mention` first, then apply Acknowledge → Anchor → Advance.",
        ]
    lines += ["", f"Current UTC time: {datetime.utcnow().isoformat(timespec='seconds')}"]
    return "\n".join(lines)
