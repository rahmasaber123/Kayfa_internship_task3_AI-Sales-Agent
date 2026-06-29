"""Kayfa Sales Agent — FastAPI Backend"""
import asyncio
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ── Path fix ──────────────────────────────────────────────────────────
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ── Kayfa imports ─────────────────────────────────────────────────────
from src.memory.mongo import get_db
from src.memory.sessions import (
    create_session, get_session, delete_session, delete_all_sessions
)
from src.memory.profile import UserProfile
from src.agent.deps import AgentDeps
from src.agent.runner import run_turn
from src.observer import Observer
from src.config import COL_TICKETS

# ── App ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Kayfa Sales Agent API",
    description="Bilingual AI Sales Agent — أكاديمية كَيفْ",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Shared resources (lazy init) ─────────────────────────────────────
_kb = None
_retriever = None
_observer = None

def get_resources():
    global _kb, _retriever, _observer
    if _kb is None:
        from src.kb.loader import load_knowledge_base
        from src.kb.retriever import HybridRetriever
        _kb = load_knowledge_base()
        _retriever = HybridRetriever()
        _observer = Observer()
    return _kb, _retriever, _observer

# ═════════════════════════════════════════════════════════════════════
# REQUEST / RESPONSE SCHEMAS
# ═════════════════════════════════════════════════════════════════════

class LoginRequest(BaseModel):
    email: str
    password: str

class LoginResponse(BaseModel):
    user_id: str
    user_name: str
    role: str
    token: str          # session token = user_id for simplicity

class SignupRequest(BaseModel):
    name: str
    email: str
    password: str
    role: str = "customer"

class NewSessionResponse(BaseModel):
    session_id: str

class ChatRequest(BaseModel):
    user_id: str
    session_id: str
    message: str
    language: str = "ar"

class ChatResponse(BaseModel):
    reply: str
    temperature: str
    session_id: str
    latency_ms: Optional[int] = None

# ═════════════════════════════════════════════════════════════════════
# AUTH GUARD
# ═════════════════════════════════════════════════════════════════════

def require_auth(x_user_id: str = Header(...)):
    """Simple header-based auth — pass user_id from login."""
    db = get_db()
    from bson import ObjectId
    try:
        user = db.users.find_one({"_id": ObjectId(x_user_id)})
    except Exception:
        user = None
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return {"user_id": str(user["_id"]), "role": user.get("role", "customer")}

def require_admin(ctx=Depends(require_auth)):
    if ctx["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return ctx

# ═════════════════════════════════════════════════════════════════════
# 1. AUTH
# ═════════════════════════════════════════════════════════════════════

@app.post("/auth/login", response_model=LoginResponse, tags=["Auth"])
def login(body: LoginRequest):
    db = get_db()
    user = db.users.find_one({"email": body.email, "password": body.password})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    uid = str(user["_id"])
    return LoginResponse(
        user_id=uid,
        user_name=user.get("name", "User"),
        role=user.get("role", "customer"),
        token=uid,
    )

@app.post("/auth/signup", tags=["Auth"])
def signup(body: SignupRequest):
    db = get_db()
    if db.users.find_one({"email": body.email}):
        raise HTTPException(status_code=409, detail="Email already registered")
    result = db.users.insert_one({
        "name": body.name,
        "email": body.email,
        "password": body.password,
        "role": body.role,
        "created_at": datetime.now(timezone.utc),
    })
    return {"user_id": str(result.inserted_id), "message": "Account created"}

# ═════════════════════════════════════════════════════════════════════
# 2. SESSIONS
# ═════════════════════════════════════════════════════════════════════

@app.post("/sessions/new", response_model=NewSessionResponse, tags=["Sessions"])
def new_session(language: str = "ar", ctx=Depends(require_auth)):
    sid = create_session(language=language)
    return NewSessionResponse(session_id=sid)

@app.get("/sessions", tags=["Sessions"])
def list_sessions(ctx=Depends(require_auth)):
    db = get_db()
    sessions = list(
        db.sessions.find(
            {"user_id": ctx["user_id"]},
            {"_id": 0}
        ).sort("created_at", -1).limit(20)
    )
    return {"sessions": sessions}

@app.get("/sessions/{session_id}", tags=["Sessions"])
def get_one_session(session_id: str, ctx=Depends(require_auth)):
    sess = get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    return sess

@app.delete("/sessions/{session_id}", tags=["Sessions"])
def remove_session(session_id: str, ctx=Depends(require_auth)):
    result = delete_session(session_id)
    return {"deleted": result}

@app.delete("/sessions", tags=["Sessions"])
def remove_all_sessions(ctx=Depends(require_auth)):
    result = delete_all_sessions()
    return {"deleted": result}

# ═════════════════════════════════════════════════════════════════════
# 3. CHAT
# ═════════════════════════════════════════════════════════════════════

@app.post("/chat/message", response_model=ChatResponse, tags=["Chat"])
async def chat(body: ChatRequest, ctx=Depends(require_auth)):
    kb, retriever, observer = get_resources()

    profile = UserProfile(session_id=body.session_id)
    deps = AgentDeps(
        user_id=body.user_id,
        session_id=body.session_id,
        kb=kb,
        retriever=retriever,
        profile=profile,
        language=body.language,
        dialect=None,
        observer=observer,
        scenario="api_chat",
    )

    # Fetch history from DB
    db = get_db()
    from src.memory.messages import load_session_messages
    history = load_session_messages(body.session_id)

    reply, _, issues = await run_turn(
        user_message=body.message,
        deps=deps,
        history=history,
        observer=observer,
        scenario="api_chat",
    )

    return ChatResponse(
        reply=reply.reply,
        temperature=reply.temperature,
        session_id=body.session_id,
    )

# ═════════════════════════════════════════════════════════════════════
# 4. CRM TICKETS
# ═════════════════════════════════════════════════════════════════════

@app.get("/crm/tickets", tags=["CRM"])
def list_tickets(
    ticket_type: Optional[str] = None,
    temperature: Optional[str] = None,
    limit: int = 50,
    ctx=Depends(require_admin),
):
    db = get_db()
    query = {}
    if ticket_type:
        query["type"] = ticket_type
    if temperature:
        query["$or"] = [
            {"temperature": {"$regex": f"^{temperature}$", "$options": "i"}},
            {"lead_data.temperature": {"$regex": f"^{temperature}$", "$options": "i"}},
        ]
    tickets = list(
        db[COL_TICKETS].find(query, {"_id": 0}).sort("created_at", -1).limit(limit)
    )
    return {"tickets": tickets, "count": len(tickets)}

@app.get("/crm/tickets/{ticket_id}", tags=["CRM"])
def get_ticket(ticket_id: str, ctx=Depends(require_admin)):
    db = get_db()
    ticket = db[COL_TICKETS].find_one({"ticket_id": ticket_id}, {"_id": 0})
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket

@app.get("/crm/stats", tags=["CRM"])
def ticket_stats(ctx=Depends(require_admin)):
    db = get_db()
    return {
        "total":       db[COL_TICKETS].count_documents({}),
        "leads":       db[COL_TICKETS].count_documents({"type": "lead"}),
        "escalations": db[COL_TICKETS].count_documents({"type": "escalation"}),
        "hot":         db[COL_TICKETS].count_documents({"$or": [{"temperature": "hot"}, {"lead_data.temperature": "hot"}]}),
        "warm":        db[COL_TICKETS].count_documents({"$or": [{"temperature": "warm"}, {"lead_data.temperature": "warm"}]}),
        "cold":        db[COL_TICKETS].count_documents({"$or": [{"temperature": "cold"}, {"lead_data.temperature": "cold"}]}),
    }

# ═════════════════════════════════════════════════════════════════════
# 5. MONITOR
# ═════════════════════════════════════════════════════════════════════

@app.get("/monitor/costs", tags=["Monitor"])
def cost_summary(ctx=Depends(require_admin)):
    db = get_db()
    pipeline_user = [
        {"$group": {
            "_id": "$user_id",
            "total_cost":      {"$sum": "$cost"},
            "llm_cost":        {"$sum": "$llm_cost"},
            "embedding_cost":  {"$sum": "$embedding_cost"},
            "messages":        {"$sum": 1},
            "conversations":   {"$addToSet": "$session_id"},
            "input_tokens":    {"$sum": "$input_tokens"},
            "output_tokens":   {"$sum": "$output_tokens"},
        }}
    ]
    per_user = list(db["usage_logs"].aggregate(pipeline_user))
    for u in per_user:
        u["conversations"] = len(u.get("conversations", []))

    totals = list(db["usage_logs"].aggregate([
        {"$group": {
            "_id": None,
            "total_cost":     {"$sum": "$cost"},
            "llm_cost":       {"$sum": "$llm_cost"},
            "embed_cost":     {"$sum": "$embedding_cost"},
            "total_messages": {"$sum": 1},
            "total_in_tok":   {"$sum": "$input_tokens"},
            "total_out_tok":  {"$sum": "$output_tokens"},
        }}
    ]))

    return {
        "global": totals[0] if totals else {},
        "per_user": per_user,
    }

@app.get("/monitor/costs/{session_id}", tags=["Monitor"])
def cost_by_session(session_id: str, ctx=Depends(require_admin)):
    db = get_db()
    logs = list(
        db["usage_logs"].find(
            {"session_id": session_id},
            {"_id": 0, "user_message": 1, "cost": 1, "llm_cost": 1,
             "embedding_cost": 1, "input_tokens": 1, "output_tokens": 1,
             "latency_ms": 1, "timestamp": 1}
        ).sort("timestamp", 1)
    )
    total = sum(l.get("cost", 0) for l in logs)
    return {"session_id": session_id, "total_cost": total, "messages": logs}

@app.get("/monitor/trace/{session_id}", tags=["Monitor"])
def trace_by_session(session_id: str, ctx=Depends(require_admin)):
    db = get_db()
    logs = list(
        db["usage_logs"].find(
            {"session_id": session_id},
            {"_id": 0}
        ).sort("timestamp", 1)
    )
    if not logs:
        raise HTTPException(status_code=404, detail="No logs for this session")
    return {"session_id": session_id, "turns": logs}

@app.get("/monitor/trace", tags=["Monitor"])
def all_traces(limit: int = 20, ctx=Depends(require_admin)):
    db = get_db()
    logs = list(
        db["usage_logs"].find({}, {"_id": 0}).sort("timestamp", -1).limit(limit)
    )
    return {"count": len(logs), "traces": logs}

# ═════════════════════════════════════════════════════════════════════
# 6. HEALTH
# ═════════════════════════════════════════════════════════════════════

@app.get("/health", tags=["System"])
def health():
    db = get_db()
    try:
        db.command("ping")
        db_status = "connected"
        collections = db.list_collection_names()
        usage_logs  = db["usage_logs"].count_documents({})
        tickets     = db[COL_TICKETS].count_documents({})
        sessions    = db["sessions"].count_documents({})
        messages    = db["messages"].count_documents({})
    except Exception as e:
        return {"status": "error", "db": "disconnected", "detail": str(e)}

    kb, _, _ = get_resources()
    return {
        "status":      "ok",
        "version":     "1.0.0",
        "db":          db_status,
        "collections": collections,
        "counts": {
            "usage_logs": usage_logs,
            "tickets":    tickets,
            "sessions":   sessions,
            "messages":   messages,
        },
        "kb_loaded": kb is not None,
    }