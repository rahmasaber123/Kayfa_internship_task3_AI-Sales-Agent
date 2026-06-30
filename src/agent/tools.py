import random
import re
import json
import time
from pathlib import Path
from typing import Annotated, Literal, Optional
from pydantic_ai import Tool, RunContext
from src.agent.deps import AgentDeps
from datetime import datetime, timezone
from src.memory.mongo import get_db
from src.crm.tickets import save_lead_ticket as _save_lead, save_escalation_ticket as _save_escalation

# ─────────────────────────────────────────────────────────────────────
# 1. Helpers
# ─────────────────────────────────────────────────────────────────────

def _validate_contact(name: Optional[str], phone: Optional[str], email: Optional[str]) -> dict:
    missing = []
    if not name or len(name.strip()) < 2: missing.append("Name")
    clean_phone = phone.strip().replace(" ", "").replace("-", "") if phone else ""
    if not clean_phone or not re.match(r"^\+\d{10,15}$", clean_phone): missing.append("Phone (+ Country Code)")
    if not email or not re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", email.strip()): missing.append("Email")
    if missing: return {"is_valid": False, "error_message": f"Required fields missing: {', '.join(missing)}"}
    return {"is_valid": True, "clean_phone": clean_phone, "clean_email": email.strip(), "clean_name": name.strip()}

def _fetch_price_from_json(program_name: str) -> str:
    try:
        root_dir = Path(__file__).resolve().parent.parent.parent
        catalog_path = next((p for p in [
            root_dir / "catalog.json",
            Path.cwd() / "catalog.json",
        ] if p.exists()), None)

        if not catalog_path:
            return "Catalog unavailable. Ask user for contact details."

        with open(catalog_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        tracks  = data.get("educational_tracks", [])
        courses = data.get("individual_courses", [])
        all_items = tracks + courses

        general = ["all","الكل","عام","كورسات","أسعار","اسعار",""]
        if not program_name or program_name.lower() in general:
            lines = [f"{i['name']}: ${i['price_usd']}" for i in all_items if i.get('price_usd')]
            return "TOP PROGRAMS:\n" + "\n".join(lines[:8])

        query = program_name.lower()

        if "full stack" in query or "فول ستاك" in query:
            return "Full Stack Track (Frontend + Backend) costs $200 USD."

        for item in all_items:
            if query in item.get("name","").lower() or item.get("name","").lower() in query:
                return f"{item['name']} costs ${item['price_usd']} USD."

        words = query.split()
        for item in all_items:
            if any(w in item.get("name","").lower() for w in words if len(w) > 3):
                return f"{item['name']} costs ${item['price_usd']} USD."

        lines = [f"{i['name']}: ${i['price_usd']}" for i in all_items if i.get('price_usd')]
        return "Program not found. Available:\n" + "\n".join(lines[:8])

    except Exception as e:
        return f"Catalog error: {e}"

# ─────────────────────────────────────────────────────────────────────
# 2. Database Tools (MongoDB: 'courses' and 'roadmaps' collections)
# ─────────────────────────────────────────────────────────────────────

@Tool
def search_courses(ctx: RunContext[AgentDeps], 
                   track: Annotated[Optional[str], "Track name (e.g., 'Web Development', 'Data Science'). MUST leave None for general search."] = None, 
                   level: Annotated[Optional[str], "Course level (e.g., 'beginner', 'advanced'). MUST leave None if unspecified."] = None) -> str:
    """
    Search for available courses. 
    
    CRITICAL INSTRUCTIONS:
    1. Call this tool ONLY ONCE per user query.
    2. If the user asks a general question (e.g., 'How to start programming?'), leave BOTH 'track' and 'level' as None to get a general overview.
    3. If this tool returns NO_RESULTS, DO NOT CALL IT AGAIN. Apologize to the user and suggest they speak with sales.
    4. NEVER loop or try multiple tracks in a row.
    """
    # 👈 LLM anti-loop Circuit Breaker
    current_calls = ctx.deps.tool_call_counts.get("search_courses", 0)
    if current_calls >= 1:
        return "FATAL ERROR: You already called search_courses. You MUST STOP using tools and reply to the user immediately based on the current context."
    ctx.deps.tool_call_counts["search_courses"] = current_calls + 1

    print(f"\n[DEBUG TOOL] search_courses called with track={track}, level={level}")
    t0 = time.time()
    try:
        db = get_db()
        query = {}
        if track: 
            safe_track = track.replace(" ", ".*")
            query["$or"] = [
                {"track": {"$regex": safe_track, "$options": "i"}},
                {"name": {"$regex": safe_track, "$options": "i"}}
            ]
        if level: 
            query["level"] = {"$regex": level, "$options": "i"}
        
        results = list(db["courses"].find(query).limit(3))
        
        if not results:
            ctx.deps.trace_buffer.append({"tool": "search_courses", "args": {"track": track, "level": level}, "result": [], "sources": [], "latency_ms": round((time.time()-t0)*1000)})
            return "NO_RESULTS: No courses found matching this criteria. DO NOT search again. Tell the user we don't have exactly this but they can contact sales."
            
        for r in results:
            if "_id" in r: r["_id"] = str(r["_id"])
            
        ctx.deps.trace_buffer.append({"tool": "search_courses", "args": {"track": track, "level": level}, "result": results[:2], "sources": [], "latency_ms": round((time.time()-t0)*1000)})
        return json.dumps(results, ensure_ascii=False)
    except Exception as e:
        ctx.deps.trace_buffer.append({"tool": "search_courses", "args": {"track": track, "level": level}, "result": f"ERROR: {e}", "sources": [], "latency_ms": round((time.time()-t0)*1000)})
        return f"ERROR: Database issue: {e}"

@Tool
def search_roadmaps(ctx: RunContext[AgentDeps], kind: Annotated[Literal["diploma", "track", "all"], "The kind of roadmap to search for"] = "all") -> str:
    """
    Retrieves structural metadata about Diplomas or Tracks (courses included, duration, skills).
    
    CRITICAL INSTRUCTIONS:
    1. Do NOT use this for deep curriculum details; use search_knowledge instead.
    2. Only call this ONCE per user turn.
    """
    print(f"\n[DEBUG TOOL] search_roadmaps called with kind={kind}")
    t0 = time.time()
    try:
        db = get_db()
        query = {}
        if kind == "diploma": query["id"] = {"$regex": "diploma", "$options": "i"}
        elif kind == "track": query["id"] = {"$regex": "track", "$options": "i"}
            
        results = list(db["roadmaps"].find(query).limit(5))
        if not results:
            ctx.deps.trace_buffer.append({"tool": "search_roadmaps", "args": {"kind": kind}, "result": [], "sources": [], "latency_ms": round((time.time()-t0)*1000)})
            return "NO_RESULTS: No roadmaps found. DO NOT search again."
            
        for r in results:
            if "_id" in r: r["_id"] = str(r["_id"])
            
        ctx.deps.trace_buffer.append({"tool": "search_roadmaps", "args": {"kind": kind}, "result": results[:2], "sources": [], "latency_ms": round((time.time()-t0)*1000)})
        return json.dumps(results, ensure_ascii=False)
    except Exception as e:
        ctx.deps.trace_buffer.append({"tool": "search_roadmaps", "args": {"kind": kind}, "result": f"ERROR: {e}", "sources": [], "latency_ms": round((time.time()-t0)*1000)})
        return f"ERROR: Database issue: {e}"

# ─────────────────────────────────────────────────────────────────────
# 3. Knowledge Base & Pricing
# ─────────────────────────────────────────────────────────────────────

@Tool
def get_pricing_catalog(ctx: RunContext[AgentDeps], program_name: Annotated[str, "The specific program name, or 'all' for general prices"] = "all") -> str:
    """
    Fetches the price of a specific program or general pricing.
    
    CRITICAL INSTRUCTIONS:
    1. Only call this ONCE.
    2. Directly use the pricing information returned to answer the user.
    """
    print(f"\n[DEBUG TOOL] get_pricing_catalog called with program_name='{program_name}'")
    t0 = time.time()
    price_data = _fetch_price_from_json(program_name)
    
    ctx.deps.trace_buffer.append({"tool": "get_pricing_catalog", "args": {"program_name": program_name}, "result": price_data[:300], "sources": ["catalog.json"], "latency_ms": round((time.time()-t0)*1000)})
    
    if price_data.startswith("PRICE_ERROR"): 
        return "STOP: Internal catalog error. Politely apologize and ask the user for their email so sales can contact them."
        
    return f"SUCCESS: Here is the pricing data to answer the user concisely: {price_data}"

@Tool
def search_knowledge(ctx: RunContext[AgentDeps], query: Annotated[str, "The search query (e.g., 'PenTest Diploma curriculum', 'refund policy')"]) -> str:
    """
    Performs deep search in the Knowledge Base for FAQs, policies, curriculums, and instructors.
    
    CRITICAL INSTRUCTIONS:
    1. Call this ONLY ONCE per turn.
    2. If NO_RESULTS is returned, do not try to rephrase the query. Just answer based on general knowledge or tell the user you don't have that info.
    """
    current_calls = ctx.deps.tool_call_counts.get("search_knowledge", 0)
    if current_calls >= 1:
        return "FATAL ERROR: You already called search_knowledge. STOP SEARCHING AND REPLY TO THE USER IMMEDIATELY."
    ctx.deps.tool_call_counts["search_knowledge"] = current_calls + 1

    print(f"\n[DEBUG TOOL] search_knowledge called with query={query}")
    t0 = time.time()
    results = ctx.deps.retriever.search(query)
    sources = [r.get("source", "") for r in (results or [])[:4] if isinstance(r, dict)]
    
    ctx.deps.trace_buffer.append({"tool": "search_knowledge", "args": {"query": query}, "result": (results or [])[:2], "sources": sources, "latency_ms": round((time.time()-t0)*1000)})
    
    if not results:
        return "NO_RESULTS: No documents found. DO NOT call this tool again. Base your answer on general knowledge or ask the user."
    return json.dumps(results, ensure_ascii=False)

# ─────────────────────────────────────────────────────────────────────
# 4. CRM Tools
# ─────────────────────────────────────────────────────────────────────

@Tool
def save_lead_ticket(ctx: RunContext[AgentDeps], 
                     summary_ar: Annotated[str, "Summary of the chat in Arabic. CRITICAL: MUST NOT hallucinate details. Only summarize what the user explicitly said. Do not invent events."], 
                     next_action_ar: Annotated[str, "Next action in Arabic"],
                     temperature: Annotated[Literal["cold", "warm", "hot"], "Lead status based on intent to buy"] = "warm",
                     user_name: Annotated[Optional[str], "User's real name"] = None, 
                     user_phone: Annotated[Optional[str], "Phone with country code"] = None,
                     user_email: Annotated[Optional[str], "Email address"] = None,
                     products_of_interest: Annotated[list[str], "Extract ALL courses/diplomas mentioned. Required."] = [],
                     goal: Annotated[str, "User's career goal. Extract if mentioned, else empty string."] = "",
                     current_level: Annotated[str, "User's current level. Extract if mentioned, else empty string."] = "",
                     buying_signals: Annotated[list[str], "Explicit signs they want to buy (e.g., asked for price, ready to pay)."] = [],
                     objections_raised: Annotated[list[str], "Concerns about price, time, etc."] = [],
                     language_spoken: Annotated[str, "Language spoken by user (e.g. 'العربية')"] = "العربية",
                     dialect_spoken: Annotated[str, "Dialect used (e.g. 'مصرية', 'سعودية')"] = "مصرية") -> str:
    """
    Persists a sales lead to the CRM. 
    Requires Name, Phone (+code), and Email.
    """
    validation = _validate_contact(user_name, user_phone, user_email)
    if not validation["is_valid"]:
        return f"ERROR: {validation['error_message']}"

    tid = _save_lead(
        session_id=ctx.deps.session_id,
        language=language_spoken,
        dialect=dialect_spoken,
        contact={"name": validation["clean_name"], "phone": validation["clean_phone"], "email": validation["clean_email"]},
        summary_ar=summary_ar,
        next_action_ar=next_action_ar,
        temperature=temperature,
        products_of_interest=products_of_interest,
        goal=goal,
        current_level=current_level,
        buying_signals=buying_signals,
        objections_raised=objections_raised,
    )
    
    ctx.deps.trace_buffer.append({"tool": "save_lead_ticket", "args": {"temperature": temperature, "summary_ar": summary_ar[:100]}, "result": f"ticket={tid}", "sources": [], "latency_ms": 0})
    return f"SUCCESS: Ticket created with ID {tid}"

@Tool
def escalate_to_human(ctx: RunContext[AgentDeps], 
                      reason: Annotated[str, "Reason for escalation"], 
                      summary_ar: Annotated[str, "Summary of the issue in Arabic"],
                      next_action_ar: Annotated[str, "Recommended next action in Arabic"],
                      user_name: Annotated[Optional[str], "User's name"] = None,
                      user_phone: Annotated[Optional[str], "User's phone"] = None,
                      user_email: Annotated[Optional[str], "User's email"] = None,
                      recommendation: Annotated[Optional[str], "Recommendation for support team"] = None,
                      products_of_interest: Annotated[Optional[list], "Products involved in the issue"] = None,
                      complaint_type: Annotated[Optional[str], "Type of complaint (refund, access, payment, technical, other)"] = None) -> str:
    """
    Escalates a complaint to the human support team and saves a ticket in the CRM.
    Call this AFTER collecting user_name, user_phone, and user_email from the user.
    """
    validation = _validate_contact(user_name, user_phone, user_email)
    if not validation["is_valid"]:
        return f"MISSING_CONTACT: {validation['error_message']} — Ask the user for these before escalating."

    ticket_id = f"ESC-{datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
    
    escalation_ticket = {
        "ticket_id": ticket_id,
        "type": "escalation",
        "created_at": datetime.now(timezone.utc),
        "contact": {
            "name": validation["clean_name"],
            "phone": validation["clean_phone"],
            "email": validation["clean_email"]
        },
        "reason": reason,
        "recommendation": recommendation,
        "summary_ar": summary_ar,
        "next_action_ar": next_action_ar,
        "products_of_interest": products_of_interest or [],
        "complaint_type": complaint_type or ""
    }
    
    get_db().tickets.insert_one(escalation_ticket)
    
    ctx.deps.trace_buffer.append({"tool": "escalate_to_human", "args": {"reason": reason, "summary_ar": summary_ar[:100]}, "result": f"ticket={ticket_id}", "sources": [], "latency_ms": 0})
    return f"SUCCESS: Escalation ticket {ticket_id} created."
    
ALL_TOOLS = [search_courses, search_roadmaps, get_pricing_catalog, search_knowledge, save_lead_ticket, escalate_to_human]
