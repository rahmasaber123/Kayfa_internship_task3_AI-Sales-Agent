"""run_turn() — one turn end-to-end: validation → detect → agent → output check → persist with financial metrics."""
import time
import logging
from datetime import datetime
from uuid import uuid4
from pydantic_ai.messages import ModelMessage

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
from src.memory.mongo import get_db
from src.observer import Observer


async def run_turn(
    *,
    user_message: str,
    deps: AgentDeps,
    history: list[ModelMessage] | None = None,
    observer: Observer | None = None,
    scenario: str = "ad_hoc",
) -> tuple[AgentReply, list[ModelMessage], list[str]]:
    """Run one turn. Returns (reply, updated_history, issues).

    Side effects: persists user + assistant turns to Mongo, updates profile,
    bumps session, logs to observer with detailed token cost matching session 10.
    """
    issues: list[str] = []
    # تهيئة الـ Observer أو سحبه من الـ deps تلقائياً
    observer = observer or getattr(deps, "observer", None) or Observer()

    # 1. Input validation
    try:
        clean = validate_input(user_message)
    except InputRejected as e:
        issues.append(f"input_rejected: {e}")
        reply = AgentReply(reply="عذرًا، الرجاء إرسال رسالة صحيحة." if deps.language == "ar"
                           else "Sorry, please send a valid message.")
        return reply, history or [], issues

    # 2. Detect injection (flagging without blocking)
    injections = detect_injection(clean)
    if injections:
        issues.append(f"injection_detected: {injections[:2]}")

    # 3. Detect language + dialect from THIS message and update deps
    lang, dialect = detect_lang(clean)
    deps.language = lang
    deps.dialect = dialect

    # 4. Competitor scan — sets the flag for dynamic instructions (Part 2 requirement)
    deps.competitor_flag = detect_competitor(clean)

    # 5. Persist user turn to MongoDB collection 'messages' (Session 8)
    save_turn(deps.session_id, "user", clean, language=lang)

    # 6. Run the agent and measure latency accurately
    t0 = time.perf_counter()
    agent = build_agent()
    result = await agent.run(clean, deps=deps, message_history=history or [])
    latency_ms = int((time.perf_counter() - t0) * 1000)

    reply: AgentReply = result.output

    # 7. Apply the profile delta the agent reported to MongoDB 'user_profiles'
    delta_dict = reply.profile_delta.model_dump(exclude_none=True, exclude_defaults=False)
    delta_dict = {k: v for k, v in delta_dict.items() if v not in (None, "", [])}
    if delta_dict:
        apply_updates(deps.profile, delta_dict)
    deps.profile.temperature = reply.temperature
    deps.profile.language = lang
    deps.profile.dialect = dialect
    save_profile(deps.profile)

    # 8. Output guardrail: check for fabricated prices
    output_issues = validate_reply(reply.reply, deps.kb)
    if output_issues:
        issues.extend(output_issues)

    # 9. Persist assistant turn to MongoDB (Session 8)
    save_turn(deps.session_id, "assistant", reply.reply, language=lang)
    touch_session(deps.session_id, language=lang, dialect=dialect)

    # 10. Financial and Token Observability (Session 10 / Part 2 Loop)
    if observer is not None:
        from src.config import MAIN_MODEL
        usage = result.usage()
        tool_names = _extract_tool_names(result.new_messages())
        
        # استدعاء دالة الـ record الخاصة بالـ Observer لحساب التكلفة وحفظ الـ event المالي
        observer.record(
            session_id=deps.session_id,
            turn_id=str(uuid4())[:8],
            scenario=scenario,
            user_message=clean,
            model=MAIN_MODEL,
            is_cache_hit=is_hit,
            tools_called=tool_names,
            tokens_in=getattr(usage, "request_tokens", 0) or 0,
            tokens_out=getattr(usage, "response_tokens", 0) or 0,
            latency_ms=latency_ms,
            language=lang,
            errors=issues,
        )

        # التحقق من الـ Cache Hit لاستخدامها في الـ Dashboard
        is_hit = False
        for msg in result.new_messages():
            if hasattr(msg, 'parts'):
                for part in msg.parts:
                    if hasattr(part, 'result') and isinstance(part.result, list):
                        for item in part.result:
                            if isinstance(item, dict) and item.get("is_cache_hit") is True:
                                is_hit = True
        
        # حفظ السجل المالي والـ Cache في usage_logs مباشرة
        db = get_db()
        db.usage_logs.insert_one({
            "user_id": deps.session_id,
            "cost": (getattr(usage, "request_tokens", 0) * 0.000003) + (getattr(usage, "response_tokens", 0) * 0.00001), # مثال تقريبي للتكلفة
            "is_cache_hit": is_hit,
            "timestamp": datetime.now()
        })

    return reply, result.all_messages(), issues


def _extract_tool_names(new_messages: list) -> list[str]:
    """Pull tool-call names from the message stream of this turn."""
    names: list[str] = []
    for msg in new_messages:
        for part in getattr(msg, "parts", []):
            name = getattr(part, "tool_name", None)
            if name and name not in names:
                names.append(name)
    return names