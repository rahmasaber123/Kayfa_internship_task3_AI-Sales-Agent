"""Load and compose prompt files. Cached so reloads are cheap."""
from functools import cache
from src.config import PROMPTS_DIR


@cache
def load(name: str) -> str:
    """Load a prompt by relative name, e.g. 'snippets/skills' or 'system/summarizer'."""
    path = PROMPTS_DIR / f"{name}.md"
    return path.read_text(encoding="utf-8")


@cache
def build_system_prompt() -> str:
    return load("snippets/system_prompt") + "\n\n---\n\n" + load("snippets/skills")


def reload_all() -> None:
    """Clear the cache. Call after editing the .md file."""
    load.cache_clear()
    build_system_prompt.cache_clear()
