"""Build the main sales agent once, register tools and dynamic instructions."""
from functools import cache
from pathlib import Path
from pydantic_ai import Agent
from src.config import MAIN_MODEL
from src.agent.deps import AgentDeps
from src.agent.schemas import AgentReply
from src.agent.tools import ALL_TOOLS

def load_prompts() -> str:
    """
    Loads system instructions and skills with unbreakable absolute path resolution.
    This prevents FileNotFoundError regardless of the terminal's working directory.
    """
    # الوصول للجذر (Root) من خلال الصعود 3 مستويات من src/agent/builder.py
    root_dir = Path(__file__).resolve().parent.parent.parent
    
    sys_prompt_path = root_dir / "prompts" / "snippets" / "system_prompt.md"
    skills_path = root_dir / "prompts" / "snippets" / "skills.md"

    # التحقق الصارم من وجود الملفات
    if not sys_prompt_path.exists():
        raise FileNotFoundError(f"CRITICAL: System prompt not found at {sys_prompt_path}")
    if not skills_path.exists():
        raise FileNotFoundError(f"CRITICAL: Skills prompt not found at {skills_path}")

    sys_prompt = sys_prompt_path.read_text(encoding="utf-8")
    skills = skills_path.read_text(encoding="utf-8")
    
    return f"{sys_prompt}\n\nSKILLS & RULES:\n{skills}"

@cache
def build_agent() -> Agent:
    """
    Builds and caches the agent instance.
    Uses temperature 0.0 for deterministic, logical sales behavior.
    """
    print(f"DEBUG: ALL_TOOLS registered: {[t.name for t in ALL_TOOLS]}")
    
    return Agent(
        model=MAIN_MODEL,
        deps_type=AgentDeps,
        output_type=AgentReply,
        system_prompt=load_prompts(), # المسار المضمون هنا
        tools=ALL_TOOLS,
        retries=2,
        model_settings={"temperature": 0.0}
    )