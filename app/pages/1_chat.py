import sys
from pathlib import Path
import streamlit as st
import asyncio
import time
import logging
import markdown as _md_lib
import re
import base64

# 🔒 Strict Security Check
if str(st.session_state.get("role", "")).lower() != "customer":
    st.switch_page("Home.py")

# ─────────────────────────────────────────────────────────────────────
# 1. Setup & Paths
# ─────────────────────────────────────────────────────────────────────
root = str(Path(__file__).resolve().parent.parent.parent)
if root not in sys.path: sys.path.append(root)

from app.ui.branding import configure_page, ICON_PATH
from app.ui.nav import render_sidebar
from src.observer import Observer

configure_page("Kayfa · Chat")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("KayfaChat")

# ─────────────────────────────────────────────────────────────────────
# 2. CSS (Dynamic LTR/RTL, Custom Bubbles, & Premium UI)
# ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    [data-testid="stChatInput"] textarea {
        unicode-bidi: plaintext !important;
        text-align: start !important;
        direction: auto !important;
    }
    
    [data-testid="stChatInput"] textarea::placeholder {
        unicode-bidi: plaintext !important;
        text-align: start !important;
        opacity: 0.8;
    }
    
    .chat-container { display: flex; flex-direction: column; width: 100%; }
    
    .custom-chat-bubble {
        padding: 18px 22px;
        border-radius: 20px;
        border: 1px solid #e0e0e0;
        background-color: #ffffff;
        margin-bottom: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.03);
        max-width: 85%;
        line-height: 1.6;
        overflow-x: auto;
    }
    
    .custom-chat-bubble p, 
    .custom-chat-bubble ul, 
    .custom-chat-bubble ol, 
    .custom-chat-bubble li,
    .custom-chat-bubble table,
    .custom-chat-bubble th,
    .custom-chat-bubble td {
        direction: inherit !important;
        text-align: inherit !important;
    }
    
    table { width: 100%; border-collapse: collapse; margin: 10px 0; }
    th, td { border: 1px solid #ddd; padding: 12px; }
    th { background-color: #f0f2f6; font-weight: bold; color: #1f2937; }
    
    .link-btn {
        background: #E77C24;
        color: white !important;
        padding: 8px 18px;
        text-decoration: none;
        border-radius: 10px;
        font-weight: bold;
        display: inline-block;
        margin-top: 12px;
        transition: background 0.3s ease, transform 0.2s ease;
    }
    .link-btn:hover { 
        background: #1A1A1A; 
        transform: translateY(-2px);
    }
    
    /* Category Headers for Suggestions */
    .suggestion-header {
        color: #6b7280;
        font-size: 1.1rem;
        font-weight: 600;
        margin-top: 20px;
        margin-bottom: 10px;
        text-align: right;
        direction: rtl;
    }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────
# 3. Helpers
# ─────────────────────────────────────────────────────────────────────
_ARABIC_RE = re.compile(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]')

def detect_direction(text: str) -> str:
    if not text: return 'ltr'
    arabic_chars = len(_ARABIC_RE.findall(text))
    return 'rtl' if arabic_chars > max(2, len(text) * 0.25) else 'ltr'

@st.cache_data
def get_icon_b64(path):
    try:
        with open(path, "rb") as f: return base64.b64encode(f.read()).decode()
    except: return ""

def stream_to_ui(placeholder, role, full_text, message_direction='ltr'):
    """Simulates real-time LLM streaming safely in the UI layer."""
    streamed_text = ""
    chunks = [full_text[i:i+4] for i in range(0, len(full_text), 4)]
    
    for chunk in chunks:
        streamed_text += chunk
        placeholder.markdown(render_custom_message(role, streamed_text, message_direction, is_final=False), unsafe_allow_html=True)
        time.sleep(0.01)
        
    placeholder.markdown(render_custom_message(role, full_text, message_direction, is_final=True), unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────
# 4. Initialization
# ─────────────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner="Initializing resources...")
def get_all_resources():
    from src.kb.loader import load_knowledge_base
    from src.kb.retriever import HybridRetriever
    from src.memory.mongo import get_db as _get_db
    from src.agent.builder import build_agent # 🚀 Import agent builder here
    
    # 🌟 Cache the built agent alongside other heavy resources
    return load_knowledge_base(), HybridRetriever(), _get_db(), Observer(), build_agent()

# Unpack the cached agent
kb, retriever, db, observer, cached_agent = get_all_resources()

def _new_session():
    from src.memory.sessions import create_session
    from src.memory.profile import UserProfile
    sid = create_session(language="ar", dialect=None)
    st.session_state.update({
        "session_id": sid, 
        "history": [], 
        "display": [], 
        "profile": UserProfile(session_id=sid),
        "query_cache": {}
    })

def _switch_session(sid):
    from src.memory.profile import UserProfile
    st.session_state.session_id = sid
    
    sess_data = db.sessions.find_one({"session_id": sid})
    if sess_data and "display" in sess_data:
        st.session_state.display = sess_data["display"]
        st.session_state.history = sess_data.get("history", [])
    else:
        st.session_state.display = []
        st.session_state.history = []
        
    st.session_state.profile = UserProfile(session_id=sid)

if "session_id" not in st.session_state: _new_session()
if "display" not in st.session_state: st.session_state.display = []
if "query_cache" not in st.session_state: st.session_state.query_cache = {}

# ─────────────────────────────────────────────────────────────────────
# 5. Sidebar (History & Management)
# ─────────────────────────────────────────────────────────────────────
render_sidebar() 

with st.sidebar:
    if st.button("➕  New chat", type="primary", use_container_width=True): 
        _new_session()
        st.rerun()
        
    st.markdown("#### Recent chats")
    if st.button("🗑 Clear all", key="clear_all_btn", use_container_width=True):
        from src.memory.sessions import delete_all_sessions
        delete_all_sessions()
        _new_session()
        st.rerun()
    
    try:
        if db is not None:
            recent_sessions = list(db.sessions.find({}, {"session_id": 1, "title": 1}).sort("created_at", -1).limit(15))
            for sess in recent_sessions:
                sid = sess["session_id"]
                raw_title = sess.get("title", f"{sid[:6]}...")
                display_title = raw_title[:22] + "..." if len(raw_title) > 22 else raw_title
                
                col1, col2 = st.columns([5, 1])
                with col1:
                    if st.button(f"💬 {display_title}", key=f"sess_{sid}", use_container_width=True, help=raw_title):
                        _switch_session(sid)
                        st.rerun()
                with col2:
                    if st.button("🗑", key=f"del_{sid}"):
                        from src.memory.sessions import delete_session
                        delete_session(sid)
                        if sid == st.session_state.session_id: _new_session()
                        st.rerun()
        else:
            st.error("Database connection lost.")
    except Exception as e: 
        logger.error(f"Sidebar history DB error: {e}")
        st.warning("Could not load chat history.")

# ─────────────────────────────────────────────────────────────────────
# 6. UI Rendering
# ─────────────────────────────────────────────────────────────────────
def render_custom_message(role: str, text: str, msg_dir: str = None, is_final: bool = False):
    if not text: return ""
    
    # Auto-detect direction individually per message to prevent shifting the whole convo
    direction = msg_dir if msg_dir else detect_direction(text)
    text_align = 'right' if direction == 'rtl' else 'left'
    
    if is_final:
        text = re.sub(r'\[([^\]]+)\]\((https?://[^\)]+)\)',
              r'<br><a href="\2" target="_blank" class="link-btn">\1 ↗</a>', text)
        text = re.sub(r'(?<!href=")(https?://[^\s<>"\)]+)',
              r'<br><a href="\1" target="_blank" class="link-btn">🔗 رابط التسجيل</a>', text)
    
    html_body = _md_lib.markdown(str(text), extensions=["extra", "sane_lists", "tables"])
     
    # If Arabic, row-reverse puts both bubbles on the right. If English, row puts them on the left.
    flex_dir = 'row-reverse' if direction == 'rtl' else 'row'
    justify = 'flex-start' 
    
    avatar = f'<img src="data:image/png;base64,{get_icon_b64(ICON_PATH)}" style="width:32px; height:32px; border-radius:4px;">' if role=='assistant' else '<div style="background:#3B47C8; color:white; width:32px; height:32px; border-radius:4px; display:flex; align-items:center; justify-content:center; font-size:16px;">👤</div>'

    return f"""
    <div style="display: flex; flex-direction: {flex_dir}; justify-content: {justify}; width: 100%; margin-bottom: 20px;" dir="ltr">
        <div style="margin: 0 10px; flex-shrink: 0; display: flex; align-items: flex-start; margin-top: 5px;">{avatar}</div>
        <div class="custom-chat-bubble" dir="{direction}" style="text-align: {text_align};">{html_body}</div>
    </div>
    """

# ─────────────────────────────────────────────────────────────────────
# 7. Main Loop (Fixed Streaming & Rerun Logic)
# ─────────────────────────────────────────────────────────────────────
st.title("💬 Kayfa Sales Chat")
sid_short = st.session_state.get("session_id", "")[:8]
st.caption(f"🔑 Session: `{sid_short}...`")

# Render chat history with auto-detection for each message independently
for msg in st.session_state.display:
    st.markdown(render_custom_message(msg["role"], msg["content"], msg_dir=None, is_final=True), unsafe_allow_html=True)

# Helper function for handling suggestion buttons immediately to avoid rendering glitches
def handle_suggestion(text):
    st.session_state.display.append({"role": "user", "content": text})
    update_data = {"display": st.session_state.display}
    if len(st.session_state.display) == 1: update_data["title"] = text
    db.sessions.update_one({"session_id": st.session_state.session_id}, {"$set": update_data}, upsert=True)
    st.rerun()

# Dashboard for new sessions
if not st.session_state.display:
    st.markdown("<h3 style='text-align: center; margin-bottom: 30px; color: #1f2937;'>مرحباً بك! كيف يمكنني مساعدتك اليوم؟ ✨</h3>", unsafe_allow_html=True)
    
    st.markdown("<div class='suggestion-header'>🎓 المسارات والدبلومات</div>", unsafe_allow_html=True)
    cols1 = st.columns(2)
    if cols1[1].button("أريد خارطة طريق دبلومة Full Stack 🗺️", use_container_width=True): 
        handle_suggestion("أريد خارطة طريق دبلومة Full Stack 🗺️")
    if cols1[0].button("ما هي تفاصيل وأسعار دبلومات الـ SOC؟ 💰", use_container_width=True): 
        handle_suggestion("ما هي تفاصيل وأسعار دبلومات الـ SOC؟ 💰")
    
    st.markdown("<div class='suggestion-header'>💡 استشارات عامة</div>", unsafe_allow_html=True)
    cols2 = st.columns(2)
    if cols2[1].button("كيف أبدأ رحلتي في تعلم البرمجة من الصفر؟ 🚀", use_container_width=True): 
        handle_suggestion("كيف أبدأ رحلتي في تعلم البرمجة من الصفر؟ 🚀")
    if cols2[0].button("هل دبلومة Data Science مناسبة لي؟ 📊", use_container_width=True): 
        handle_suggestion("هل دبلومة Data Science مناسبة لي؟ 📊")

# Normal Chat Input
user_input = st.chat_input("اكتب رسالتك… type your message")

if user_input:
    logger.info(f"DEBUG: Processing message: {user_input}")
    
    if "query_cache" not in st.session_state: st.session_state.query_cache = {}
        
    st.session_state.display.append({"role": "user", "content": user_input})
    
    # Save to DB
    update_data = {"display": st.session_state.display}
    if len(st.session_state.display) == 1: update_data["title"] = user_input
    db.sessions.update_one({"session_id": st.session_state.session_id}, {"$set": update_data}, upsert=True)
    
    # 🌟 IMPORTANT: Rerun once to show the user message immediately
    st.rerun()

# If an actual message exists in state (and we aren't in a loop), process Agent
elif len(st.session_state.display) > 0 and st.session_state.display[-1]["role"] == "user":
    last_msg = st.session_state.display[-1]["content"]
    
    from src.agent.deps import AgentDeps
    from src.agent.runner import run_turn
    
    deps = AgentDeps(
        user_id="guest", 
        session_id=st.session_state.session_id, 
        kb=kb, 
        retriever=retriever, 
        profile=st.session_state.profile, 
        language="ar", 
        dialect=None, 
        observer=observer, 
        scenario="streamlit_chat"
    )
    
    _dir = detect_direction(last_msg)
    _thinking = "⏳ كيف ايجنت  بيفكر..." if _dir == 'rtl' else "⏳ Kayfa Agent is thinking..."
    
    # Override the spinner direction and alignment dynamically using CSS
    st.markdown(f"""
    <style>
        div[data-testid="stStatusWidget"] {{
            direction: {_dir};
            display: flex;
            justify-content: {"flex-end" if _dir == 'rtl' else "flex-start"};
            border: none !important;
            background: transparent !important;
        }}
    </style>
    """, unsafe_allow_html=True)
    
    try:
        # We use an empty container to hold the spinner so we can remove it instantly upon completion
        status_container = st.empty()
        with status_container.container():
            with st.status(_thinking, expanded=True):
                reply, new_history, issues = asyncio.run(run_turn(
                    user_message=last_msg, 
                    deps=deps, 
                    history=st.session_state.history,
                    agent=cached_agent # 🌟 Pass the cached agent here!
                ))
                reply_text = reply.reply
                
        # 🧨 REMOVE the spinner entirely before starting the stream
        status_container.empty()
        
        # Determine stream direction based on actual agent text, not user's previous text
        reply_dir = detect_direction(reply_text)
        
        reply_placeholder = st.empty()
        stream_to_ui(reply_placeholder, "assistant", reply_text, reply_dir)
        
        st.session_state.display.append({"role": "assistant", "content": reply_text})
        st.session_state.history = new_history
        db.sessions.update_one({"session_id": st.session_state.session_id}, {"$set": {"display": st.session_state.display}}, upsert=True)
        
    except Exception as e:
        logger.error(f"Agent crash: {e}", exc_info=True) 
        st.error(f"Error: {e}")
