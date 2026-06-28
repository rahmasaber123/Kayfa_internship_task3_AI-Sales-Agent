"""Kayfa Sales Agent — Streamlit entry point.
Handles user-based authentication, then renders a minimal branded landing page.
"""
import sys
from pathlib import Path

# 1. Path injection MUST happen before ANY 'src' imports
ROOT = Path(__file__).resolve().parent.parent 
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# 2. Now we can safely import everything
import streamlit as st
import logging
from pymongo.errors import CollectionInvalid

from app.ui.branding import configure_page, render_logo, KAYFA_BLUE

from src.memory.mongo import get_db, setup_collections, setup_vector_index 
from src.kb.loader import load_knowledge_base
from src.kb.retriever import build_and_persist_chunks
from src.memory.cache import setup_cache_index

logger = logging.getLogger("KayfaInit")

@st.cache_resource(show_spinner="Initializing Database & Knowledge Base...")
def run_one_time_setup():
    """Runs exactly once per server boot to ensure DB is prepped."""
    try:
        db = get_db()
        
        # 1. Force-create usage_logs for the Monitoring dashboard
        if "usage_logs" not in db.list_collection_names():
            try:
                db.create_collection("usage_logs")
                logger.info("✅ Created 'usage_logs' collection.")
            except CollectionInvalid:
                pass 
                
        # 2. Setup standard indexes
        logger.info("⚙️ Setting up MongoDB indexes...")
        setup_collections()
        
        # 3. Setup Semantic Cache Index
        logger.info("⚙️ Setting up Semantic Cache Index...")
        setup_cache_index()
        
        # 4. Auto-build KB chunks if wiped/empty
        if "kb_chunks" not in db.list_collection_names() or db.kb_chunks.count_documents({}) == 0:
            logger.info("🚀 KB is empty! Starting atomic chunk build...")
            kb = load_knowledge_base()
            build_and_persist_chunks(kb, force=True)
            
            idx_status = setup_vector_index()
            logger.info(f"✅ Vector Index Status: {idx_status}")
        else:
            logger.info("✅ KB already populated. Skipping rebuild.")
            
        return True
    
    except Exception as e:
        logger.error(f"❌ Initialization failed: {e}")
        return False


run_one_time_setup()


def _check_credentials() -> bool:
    """Show login form with email/password against MongoDB."""
    if st.session_state.get("authenticated"):
        return True

    left, mid, right = st.columns([1, 2, 1])
    with mid:
        st.markdown("<div style='height: 80px;'></div>", unsafe_allow_html=True)
        render_logo(width=200)
        st.markdown(
            "<h2 style='margin-top: 30px;'>Sales Agent — System Access</h2>"
            "<p style='color: #6B7280; margin-bottom: 30px;'>"
            "Please log in with your credentials."
            "</p>",
            unsafe_allow_html=True,
        )

        with st.form("login_form", clear_on_submit=False):
            email = st.text_input("Email", placeholder="admin@kayfa.com")
            password = st.text_input("Password", type="password", placeholder="Password")
            submitted = st.form_submit_button("Sign In", type="primary", use_container_width=True)

        if submitted:
            db = get_db()
            user = db.users.find_one({"email": email, "password": password})
            
            if user:
                st.session_state.authenticated = True
                # حفظ الهوية لربطها بالـ AgentDeps لاحقاً
                st.session_state.user_id = str(user["_id"])
                st.session_state.user_name = user.get("name", "User")
                st.session_state.role = user.get("role", "customer")
                st.rerun()
            else:
                st.error("Invalid email or password.")

    return False

if not _check_credentials():
    st.stop()


# ─────────────────────────────────────────────────────────────────────
# Authenticated — minimal landing
# ─────────────────────────────────────────────────────────────────────

with st.sidebar:
    render_logo(width=140)
    st.markdown("---")
    st.write(f"Logged in as: **{st.session_state.role.upper()}**")
    
    # تحديث احترافي للروابط باستخدام page_link لتجنب الـ API Errors
    st.page_link("pages/1_chat.py", label="💬 Chat Agent", icon="💬")
    
    # إضافة روابط الوصول للوحة الأدمن فقط
    if st.session_state.get("role") == "admin":
        st.markdown("---")
        st.markdown("### ⚙️ Admin Tools")
        st.page_link("pages/2_Tickets.py", label="🎫 CRM Tickets", icon="🎫")
        st.page_link("pages/3_Monitoring.py", label="📊 System Monitoring", icon="📊")

    st.markdown("---")
    if st.button("Sign out", use_container_width=True):
        st.session_state.clear()
        st.rerun()

# Centered hero
left, center, right = st.columns([1, 3, 1])
with center:
    st.markdown("<div style='height: 60px;'></div>", unsafe_allow_html=True)
    render_logo(width=240)
    st.markdown(
        f"""
        <div style='text-align: center; margin-top: 32px;'>
            <h1 style='color: #1A1F4D; font-weight: 700; margin: 0;'>
                Sales Agent
            </h1>
            <p style='color: #6B7280; font-size: 16px; margin-top: 8px;'>
                Bilingual AI assistant · مساعد ذكي ثنائي اللغة
            </p>
            <p style='text-align: center; color: #6B7280; font-size: 14px; margin-top: 40px;'>
                Use the sidebar to navigate to
                <strong style='color: {KAYFA_BLUE};'>chat</strong>
                or
                <strong style='color: {KAYFA_BLUE};'>Tickets</strong>.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
