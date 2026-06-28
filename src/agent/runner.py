import time
from uuid import uuid4
from pydantic_ai.messages import ModelMessage
# إضافة الاستيراد اللازم للـ Config
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
    *,
    user_message: str,
    deps: AgentDeps,
    history: list[ModelMessage] | None = None,
    observer: Observer | None = None,
    scenario: str = "ad_hoc",
) -> tuple[AgentReply, list[ModelMessage], list[str]]:
    
    issues: list[str] = []
    observer = observer or getattr(deps, "observer", None) or Observer()

    # 1. Input validation & Guardrails
    try:
        clean = validate_input(user_message)
    except InputRejected as e:
        reply = AgentReply(reply="عذرًا، الرسالة غير صالحة." if deps.language == "ar" else "Sorry, invalid message.")
        return reply, history or [], [f"input_rejected: {e}"]

    injections = detect_injection(clean)
    if injections:
        reply = AgentReply(reply="عذراً، لا يمكنني تلبية هذا الطلب." if deps.language == "ar" else "I cannot fulfill this request.")
        return reply, history or [], ["injection_detected"]

    lang, dialect = detect_lang(clean)
    deps.language, deps.dialect = lang, dialect
    deps.competitor_flag = detect_competitor(clean)

    save_turn(user_id=deps.user_id, session_id=deps.session_id, role="user", content=clean, language=lang)

    # 6. Run agent
    t0 = time.perf_counter()
    agent = build_agent()
    
    result = await agent.run(
        clean, 
        deps=deps, 
        message_history=history or [],
    )
    latency_ms = int((time.perf_counter() - t0) * 1000)

    # الوصول للرد
    reply: AgentReply = result.output

    # 7. Apply profile updates
    delta_dict = reply.profile_delta.model_dump(exclude_none=True) if reply.profile_delta else {}
    if delta_dict:
        apply_updates(deps.profile, delta_dict)
        save_profile(deps.profile)

    # 8. Output guardrail
    output_issues = validate_reply(reply.reply)
    if output_issues:
        issues.extend(output_issues)
        reply.reply = "عذراً، أواجه مشكلة في معالجة الرد." if lang == "ar" else "Sorry, I am having trouble processing the response."

    save_turn(user_id=deps.user_id, session_id=deps.session_id, role="assistant", content=reply.reply, language=lang)
    touch_session(deps.session_id, language=lang, dialect=dialect)

    # 9. Observability & Financial Metrics (Extraction Phase)
    usage = result.usage
    usage_dict = usage.model_dump() if hasattr(usage, "model_dump") else {}
    
    tokens_in = usage_dict.get('request_tokens') or usage_dict.get('prompt_tokens') or 0
    tokens_out = usage_dict.get('response_tokens') or usage_dict.get('completion_tokens') or 0
    
    trace_data = _extract_deep_trace(result.new_messages())
    used_rag = any(step.get("tool") == "search_knowledge" for step in trace_data)
    
    # اكتشاف هل تم استخدام الكاش في هذا الـ turn
    is_hit = False
    for msg in result.new_messages():
        if hasattr(msg, 'parts'):
            for part in msg.parts:
                if hasattr(part, 'content') and isinstance(part.content, list):
                    for item in part.content:
                        if isinstance(item, dict) and item.get("is_cache_hit") is True:
                            is_hit = True

    # 10. Financial Calculation (Calculated based on 10 RAG chunks)
    # أسعار تقريبية (استخدم القيم الرسمية لـ OpenAI)
    LLM_INPUT_RATE = 0.00000015  # $0.15 per 1M tokens (GPT-4o-mini reference)
    LLM_OUTPUT_RATE = 0.00000060 
    
    # التكلفة الثابتة للـ 10 Chunks (استخدام الـ Embedding)
    RAG_CHUNK_COST = 0.00000002 * 10 
    
    # التكلفة الثابتة لكل استدعاء أداة (Tool)
    TOOL_COST_PER_CALL = 0.00005 
    
    llm_cost = (tokens_in * LLM_INPUT_RATE) + (tokens_out * LLM_OUTPUT_RATE)
    tool_cost = len(trace_data) * TOOL_COST_PER_CALL
    embedding_cost = RAG_CHUNK_COST if used_rag else 0.0
    
    total_cost = llm_cost + tool_cost + embedding_cost

    # 11. Record to Observer (تمرير كل شيء بدقة)
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
            trace=trace_data,
            latency_ms=latency_ms, 
            language=lang, 
            errors=issues
        )

    return reply, result.all_messages(), issues

def _extract_deep_trace(new_messages: list) -> list[dict]:
    """Extracts exact tool arguments and returns for Monitor B."""
    trace = []
    for msg in new_messages:
        for part in getattr(msg, "parts", []):
            part_type = type(part).__name__
            if part_type == "ToolCallPart":
                trace.append({
                    "type": "tool_call", 
                    "tool": getattr(part, "tool_name", "unknown"), 
                    "args": getattr(part, "args", {})
                })
            elif part_type == "ToolReturnPart":
                # التأكد من استخراج المحتوى
                content = getattr(part, "content", "")
                content_str = str(content)
                trace.append({
                    "type": "tool_return", 
                    "tool": getattr(part, "tool_name", "unknown"), 
                    "result": content_str[:500] + "..." if len(content_str) > 500 else content_str
                })
    return trace