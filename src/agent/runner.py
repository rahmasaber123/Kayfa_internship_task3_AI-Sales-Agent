import time
from uuid import uuid4
from pydantic_ai.messages import ModelMessage
from pydantic_ai.usage import UsageLimits
from pydantic_ai.exceptions import UsageLimitExceeded

from src.config import MAIN_MODEL
from src.agent.builder import build_agent
from src.agent.deps import AgentDeps
from src.agent.schemas import AgentReply
from src.guardrails.input import validate_input, InputRejected
from src.guardrails.injection import detect_injection
from src.guardrails.competitor import detect_competitor
from src.guardrails.output import validate_reply
from src.lang.detect import detect as detect_lang
from src.memory.messages import save_turn
from src.memory.sessions import touch_session
from src.memory.profile import apply_updates, save_profile
from src.observer import Observer


async def run_turn(
    user_message: str,
    deps: AgentDeps,
    history: list[ModelMessage] | None = None,
    observer: Observer | None = None,
    scenario: str = "ad_hoc",
) -> tuple[AgentReply, list[ModelMessage], list[str]]:

    issues: list[str] = []
    observer = observer or getattr(deps, "observer", None) or Observer()

    # 1. Input validation
    try:
        clean = validate_input(user_message)
    except InputRejected as e:
        reply = AgentReply(reply="عذرًا، الرسالة غير صالحة." if deps.language == "ar" else "Sorry, invalid message.")
        return reply, history or [], [f"input_rejected: {e}"]

    # 2. Injection guard
    if detect_injection(clean):
        reply = AgentReply(reply="عذراً، لا يمكنني تلبية هذا الطلب." if deps.language == "ar" else "I cannot fulfill this request.")
        return reply, history or [], ["injection_detected"]

    # 3. Language & flags
    lang, dialect = detect_lang(clean)
    deps.language, deps.dialect = lang, dialect
    deps.competitor_flag = detect_competitor(clean)

    save_turn(user_id=deps.user_id, session_id=deps.session_id, role="user", content=clean, language=lang)
    
    # 3.5 Complaint detection (Optimized)
    COMPLAINT_KEYWORDS = {"دفعت", "فلوسي", "مش شغال", "خدمة وحشة", "استرداد", "refund", "not working", "paid", "مش راضي", "عايز فلوسي"}
    
    # Use sets for O(1) lookup speed instead of list iteration
    if any(kw in clean for kw in COMPLAINT_KEYWORDS):
        clean = f"[SYSTEM: The user is expressing a complaint. Follow Escalation Flow 9-B. If you have not asked for contact info yet, do Step 1. If you have, do Step 2 and call escalate_to_human.]\n{clean}"

    # 4. Run agent
    t0 = time.perf_counter()
    agent = build_agent()

    try:
        result = await agent.run(
            clean,
            deps=deps,
            message_history=history or [],
            usage_limits=UsageLimits(request_limit=5),
        )
    except UsageLimitExceeded:
        fallback = "آسف، في مشكلة تقنية دلوقتي. ممكن تكتب رسالتك تاني؟" if lang == "ar" else "Sorry, a technical issue occurred. Please try again."
        return AgentReply(reply=fallback), history or [], ["usage_limit_exceeded"]

    latency_ms = int((time.perf_counter() - t0) * 1000)

    # 5. Extract reply (Safely handle both string and AgentReply based on pydantic-ai version)
    raw_output = getattr(result, 'data', None)
    if raw_output is None:
        raw_output = getattr(result, 'output', None)
        
    if isinstance(raw_output, str):
        reply = AgentReply(reply=raw_output)
    elif hasattr(raw_output, 'reply'):
        reply = raw_output
    else:
        reply = AgentReply(reply=str(raw_output))

    print("========== AGENT RESPONSE DEBUG ==========")
    print(f"User: {clean}")
    print(f"Reply: '{reply.reply}'")
    print("==========================================")

    # 6. Profile updates
    delta_dict = {}
    if hasattr(reply, 'profile_delta') and reply.profile_delta:
        delta_dict = reply.profile_delta.model_dump(exclude_none=True)
        
    if delta_dict:
        apply_updates(deps.profile, delta_dict)
        save_profile(deps.profile)

    # 7. Output guardrail
    output_issues = validate_reply(reply.reply)
    if output_issues:
        issues.extend(output_issues)
        reply.reply = "عذراً، أواجه مشكلة في معالجة الرد." if lang == "ar" else "Sorry, I am having trouble processing the response."

    save_turn(user_id=deps.user_id, session_id=deps.session_id, role="assistant", content=reply.reply, language=lang)
    touch_session(deps.session_id, language=lang, dialect=dialect)

    # 8. Usage & cost
    usage = result.usage() if callable(getattr(result, "usage", None)) else getattr(result, "usage", None)
    
    tokens_in = getattr(usage, 'request_tokens', None) or getattr(usage, 'prompt_tokens', None) or 0
    tokens_out = getattr(usage, 'response_tokens', None) or getattr(usage, 'completion_tokens', None) or 0
    
    if tokens_in == 0 and clean:
        tokens_in = len(clean) // 4
    if tokens_out == 0 and reply.reply:
        tokens_out = len(reply.reply) // 4

    # We now fetch usage directly from the request-isolated dependency trace buffer!
    used_rag = any(step.get("tool") == "search_knowledge" for step in deps.trace_buffer)

    is_hit = False
    new_messages = result.new_messages() if callable(getattr(result, "new_messages", None)) else getattr(result, "new_messages", [])
    
    for msg in new_messages:
        if hasattr(msg, 'parts'):
            for part in msg.parts:
                if hasattr(part, 'content') and isinstance(part.content, list):
                    for item in part.content:
                        if isinstance(item, dict) and item.get("is_cache_hit") is True:
                            is_hit = True

    LLM_INPUT_RATE  = 0.15  / 1_000_000
    LLM_OUTPUT_RATE = 0.60  / 1_000_000
    EMBEDDING_RATE  = 0.02  / 1_000_000

    llm_cost       = (tokens_in * LLM_INPUT_RATE) + (tokens_out * LLM_OUTPUT_RATE)
    embedding_tokens = 500 if used_rag else 0
    embedding_cost = embedding_tokens * EMBEDDING_RATE
    tool_cost      = 0.0
    total_cost     = llm_cost + embedding_cost + tool_cost
    
    # 9. Observer
    if observer is not None:
        observer.record(
            user_id=deps.user_id,
            session_id=deps.session_id,
            turn_id=str(uuid4())[:8],
            scenario=scenario,
            user_message=clean,
            assistant_reply=reply.reply,
            model=MAIN_MODEL,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            llm_cost=llm_cost,
            embedding_cost=embedding_cost,
            tool_cost=tool_cost,
            cost=total_cost,
            used_rag=used_rag,
            is_cache_hit=is_hit,
            latency_ms=latency_ms,
            trace=deps.trace_buffer,
            language=lang,
            errors=issues,
        )
        
        deps.trace_buffer.clear()
        deps.tool_call_counts.clear()
        
    all_msgs = result.all_messages() if callable(getattr(result, "all_messages", None)) else getattr(result, "all_messages", [])
    return reply, all_msgs, issues