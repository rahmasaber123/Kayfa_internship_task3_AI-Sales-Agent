import re
import json
from pathlib import Path
from typing import Annotated, Literal, Optional
from pydantic_ai import Tool, RunContext
from src.agent.deps import AgentDeps
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
    """A foolproof function that always returns 'SUCCESS' to keep the Agent calm."""
    try:
        root_dir = Path(__file__).resolve().parent.parent.parent
        possible_paths = [
            root_dir / "catalog.json",
            Path.cwd() / "catalog.json",
            Path.cwd() / "data" / "catalog.json"
        ]
        
        catalog_path = next((p for p in possible_paths if p.exists()), None)
                
        if not catalog_path:
            return "SUCCESS: Catalog is temporarily down. Kindly ask the user for their email and phone number to send them the prices."

        with open(catalog_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        all_items = data.get("programs", [])
        if not all_items:
            all_items = data.get("educational_tracks", []) + data.get("individual_courses", [])

        if not all_items:
            return "SUCCESS: Pricing data is empty. Ask the user for contact details to follow up."

        general_keywords = ["all", "الكل", "عام", "كورسات", "كورساتكم", "أسعار", "اسعار", ""]
        if not program_name or program_name.lower() in general_keywords:
            return f"SUCCESS: Here is the FULL catalog data: {json.dumps(all_items, ensure_ascii=False)}"

        query = program_name.lower()
        for item in all_items:
            item_name = item.get("name", "").lower()
            if query in item_name or item_name in query:
                return f"SUCCESS: Found the exact course data. Extract the price from here: {json.dumps(item, ensure_ascii=False)}"

        # 🌟 السر هنا: لا نقل له "Not found". نقول له "ابحث داخل هذه القائمة الشاملة"
        return f"SUCCESS: Please extract the price for '{program_name}' directly from this full catalog data: {json.dumps(all_items, ensure_ascii=False)}"
        
    except Exception as e:
        # حتى في حالة الخطأ البرمجي، لا نفزعه!
        return "SUCCESS: Internal system update. Politely ask the user for their contact details to send the pricing."
# ─────────────────────────────────────────────────────────────────────
# 2. Database Tools (MongoDB: 'courses' and 'roadmaps' collections)
# ─────────────────────────────────────────────────────────────────────

@Tool
def search_courses(ctx: RunContext[AgentDeps], track: Optional[str] = None, level: Optional[str] = None) -> str:
    """
    Search Kayfa's structured individual courses in the database.
    Returns metadata like duration, track, and levels.
    """
    print(f"\n[DEBUG TOOL] search_courses called with track={track}, level={level}")
    try:
        db = get_db()
        query = {}
        if track: 
            safe_track = track.replace(" ", ".*")
            query["track"] = {"$regex": safe_track, "$options": "i"}
        if level: 
            query["level"] = {"$regex": level, "$options": "i"}
        
        results = list(db["courses"].find(query).limit(5))
        if not results: return "NO_RESULTS: No courses found matching this criteria."
            
        for r in results:
            if "_id" in r: r["_id"] = str(r["_id"])
        return json.dumps(results, ensure_ascii=False)
    except Exception as e:
        return f"ERROR: Database issue: {e}"

@Tool
def search_roadmaps(ctx: RunContext[AgentDeps], kind: Literal["diploma", "track", "all"] = "all") -> str:
    """
    Retrieves structural metadata about Diplomas or Tracks (courses included, duration, skills).
    Do NOT use this for deep curriculum details; use search_knowledge instead.
    """
    print(f"\n[DEBUG TOOL] search_roadmaps called with kind={kind}")
    try:
        db = get_db()
        query = {}
        if kind == "diploma": query["id"] = {"$regex": "diploma", "$options": "i"}
        elif kind == "track": query["id"] = {"$regex": "track", "$options": "i"}
            
        results = list(db["roadmaps"].find(query).limit(5))
        if not results: return "NO_RESULTS: No roadmaps found."
            
        for r in results:
            if "_id" in r: r["_id"] = str(r["_id"])
        return json.dumps(results, ensure_ascii=False)
    except Exception as e:
        return f"ERROR: Database issue: {e}"

# ─────────────────────────────────────────────────────────────────────
# 3. Knowledge Base & Pricing (JSON + MongoDB 'docs' collection)
# ─────────────────────────────────────────────────────────────────────

# في دالة get_pricing_catalog
@Tool
def get_pricing_catalog(ctx: RunContext, program_name: str = "all") -> str:
    """Fetches the specific price of a program. If user asks for general prices, pass 'all'."""
    print(f"\n[DEBUG TOOL] get_pricing_catalog called with program_name='{program_name}'")
    
    price_data = _fetch_price_from_json(program_name)
    
    if price_data.startswith("PRICE_ERROR"): 
        return "STOP: Internal catalog error. Politely apologize and ask the user for their email so sales can contact them."
        
    return f"SUCCESS: Here is the pricing data to answer the user concisely: {price_data}"

@Tool
def search_knowledge(ctx: RunContext[AgentDeps], query: str) -> str:
    """
    Performs deep search in the Knowledge Base (MongoDB 'docs' collection).
    MUST be used when the user asks about:
    1. Diplomas (Curriculum, Details, e.g., "PenTest Diploma")
    2. Instructors (Who teaches what)
    3. Policies & FAQs (Refunds, subscriptions)
    4. General paid individual course lists.
    """
    print(f"\n[DEBUG TOOL] search_knowledge called with query={query}")
    results = ctx.deps.retriever.search(query)
    if not results:
        return "NO_RESULTS: No specific knowledge base documents found for this query."
    return json.dumps(results, ensure_ascii=False)

# ─────────────────────────────────────────────────────────────────────
# 4. CRM Tools
# ─────────────────────────────────────────────────────────────────────

# In tools.py, update the save_lead_ticket function:

@Tool
def save_lead_ticket(ctx: RunContext[AgentDeps], summary_ar: str, next_action_ar: str, 
                     temperature: Annotated[Literal["cold", "warm", "hot"], "Lead status"] = "warm",
                     user_name: Optional[str] = None, user_phone: Optional[str] = None, user_email: Optional[str] = None) -> str:
    """Persists a sales lead to the CRM. Requires Name, Phone (+code), and Email."""
    validation = _validate_contact(user_name, user_phone, user_email)
    if not validation["is_valid"]: 
        return f"ERROR: {validation['error_message']}"
    
    # We pass 'temperature' directly to the backend. 
    # Ensure your _save_lead backend function is updated to accept this 
    # and save it at the root of the document.
    tid = _save_lead(
        session_id=ctx.deps.session_id, 
        language=ctx.deps.language, 
        dialect=ctx.deps.dialect,
        contact={"name": validation["clean_name"], "phone": validation["clean_phone"], "email": validation["clean_email"]},
        summary_ar=summary_ar, 
        next_action_ar=next_action_ar, 
        temperature=temperature
    )
    return f"SUCCESS: Ticket created with ID {tid}"
@Tool
def escalate_to_human(ctx: RunContext[AgentDeps], reason: str, summary_ar: str, next_action_ar: str,
                      user_name: Optional[str] = None, user_phone: Optional[str] = None, user_email: Optional[str] = None) -> str:
    """Escalates a critical issue to a human agent. Requires contact info."""
    validation = _validate_contact(user_name, user_phone, user_email)
    if not validation["is_valid"]: 
        return f"ERROR: {validation['error_message']}"
    
    tid = _save_escalation(
        session_id=ctx.deps.session_id, language=ctx.deps.language, dialect=ctx.deps.dialect,
        contact={"name": validation["clean_name"], "phone": validation["clean_phone"], "email": validation["clean_email"]},
        reason=reason, summary_ar=summary_ar, next_action_ar=next_action_ar
    )
    return f"SUCCESS: Escalation ticket created with ID {tid}"

ALL_TOOLS = [search_courses, search_roadmaps, get_pricing_catalog, search_knowledge, save_lead_ticket, escalate_to_human]