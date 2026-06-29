from functools import cache
from pydantic_ai import Agent, RunContext
from src.config import MAIN_MODEL
from src.agent.deps import AgentDeps
from src.agent.tools import ALL_TOOLS

def load_prompts() -> str:
    from src.prompts import load
    system = load("snippets/system_prompt")
    skills = load("snippets/skills")
    return f"{system}\n\n---\n\n{skills}"

# 1. Initialize the agent WITHOUT result_type/output_type to fix compatibility with older pydantic-ai versions
_agent = Agent(
    model=MAIN_MODEL,
    deps_type=AgentDeps,
    tools=ALL_TOOLS,
    retries=2,
    model_settings={"temperature": 0.3}
)

# 2. Add the dynamic system prompt decorator
@_agent.system_prompt
def add_dynamic_instructions(ctx: RunContext[AgentDeps]) -> str:
    base_prompt = load_prompts()
    
    # Build dynamic instructions based on current user context (AgentDeps)
    dynamic_instructions = []
    
    # Force language & dialect matching
    if ctx.deps.language:
        dynamic_instructions.append(f"CRITICAL: The user is speaking {ctx.deps.language}.")
    if ctx.deps.dialect:
        dynamic_instructions.append(f"CRITICAL: The user's dialect is {ctx.deps.dialect}. You MUST mirror this dialect.")
        
    # Competitor handling
    if ctx.deps.competitor_flag:
        dynamic_instructions.append(f"NOTE: The user mentioned a competitor ({ctx.deps.competitor_flag}). Highlight our unique value gracefully.")
        
    # Scenario context
    if ctx.deps.scenario:
        dynamic_instructions.append(f"CURRENT SCENARIO: {ctx.deps.scenario}")

    # Combine the static prompts with the dynamic context
    if dynamic_instructions:
        return base_prompt + "\n\n[DYNAMIC CONTEXT FOR THIS TURN]\n" + "\n".join(dynamic_instructions)
    
    return base_prompt

@cache
def build_agent() -> Agent:
    print(f"DEBUG: ALL_TOOLS registered: {[t.name for t in ALL_TOOLS]}")
    return _agent