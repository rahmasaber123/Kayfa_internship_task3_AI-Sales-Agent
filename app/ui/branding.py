"""Kayfa branding — colors, CSS, logo rendering. Intelligent LTR/RTL handling."""
from pathlib import Path
import streamlit as st

# ─── Brand palette ───
KAYFA_BLUE   = "#3B47C8"
KAYFA_NAVY   = "#1A1F4D"
KAYFA_LIGHT  = "#E8ECFF"
KAYFA_DEEP   = "#2A35A8"
TEXT_PRIMARY = "#1A1F4D"
TEXT_MUTED   = "#6B7280"

# ─── Asset paths ───
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
LOGO_PATH = str(ASSETS_DIR / "kayfa_logo.png")
ICON_PATH = str(ASSETS_DIR / "kayfa_icon.png")

def configure_page(title: str = "Kayfa Sales Agent", login_mode: bool = False):
    st.set_page_config(
        page_title=title,
        page_icon=ICON_PATH,
        layout="centered" if login_mode else "wide",
        initial_sidebar_state="collapsed" if login_mode else "expanded",
    )
    _inject_css()
    if login_mode:
        st.markdown(
            """<style>
            [data-testid="stSidebarCollapsedControl"],
            [data-testid="stSidebar"] { display: none !important; }
            </style>""",
            unsafe_allow_html=True,
        )

def render_logo(width: int = 160):
    st.image(LOGO_PATH, width=width)

def _inject_css():
    css = f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700&display=swap');

    html, body, [class*="css"], [data-testid="stAppViewContainer"] {{
        font-family: 'Tajawal', sans-serif;
    }}

    /* ───────────────────────────────────────────────────────── */
    /* ─── INTELLIGENT CHAT ALIGNMENT (AUTO DIR) ─────────────── */
    /* ───────────────────────────────────────────────────────── */
    
    /* استخدام auto يجعل المتصفح يكتشف اللغة تلقائياً */
    [data-testid="stChatMessage"] {{
       text-align: right !important;
      direction: rtl !important;
    }}
    
    div[data-testid="stChatMessageContent"] {{
        text-align: right !important;
       direction: rtl !important;
    }}

    .custom-chat-bubble {{
       text-align: right !important;
       direction: rtl !important;
    }}

    /* 1. LINKS AS BLUE BUTTONS */
    .custom-chat-bubble a {{
        display: inline-block;
        background: {KAYFA_BLUE} !important;
        color: #FFFFFF !important;
        padding: 8px 16px !important;
        border-radius: 8px !important;
        text-decoration: none !important;
        font-weight: 700 !important;
        margin: 8px 0 !important;
        border: 1px solid {KAYFA_DEEP} !important;
        text-align: center !important;
        transition: background 0.2s ease;
    }}
    .custom-chat-bubble a:hover {{
        background: {KAYFA_DEEP} !important;
    }}

    /* 2. BOLD TEXT HIERARCHY */
    .custom-chat-bubble strong, .custom-chat-bubble b {{
        font-weight: 800 !important;
        color: {KAYFA_NAVY} !important;
    }}

    /* Sidebar Aesthetics */
    [data-testid="stSidebar"] {{ background: {KAYFA_NAVY} !important; }}
    [data-testid="stSidebar"] * {{ color: #FFFFFF !important; }}
    
    [data-testid="stSidebar"] .stButton button {{
        background: rgba(255,255,255,0.08);
        color: #FFFFFF !important;
        border: 1px solid rgba(255,255,255,0.15);
        text-align: start !important; /* Fixed alignment */
        padding: 8px 12px;
        border-radius: 8px;
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)