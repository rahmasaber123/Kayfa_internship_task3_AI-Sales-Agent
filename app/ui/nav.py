import streamlit as st
import uuid
from app.ui.branding import render_logo

def perform_logout():
    """Clear session state and force navigation to the Login page safely."""
    st.session_state.clear()
    try:
        # Ensure this matches your login file name exactly (case-sensitive)
        st.switch_page("Login.py")
    except Exception:
        # Safely halt execution to prevent infinite reloading loops
        st.warning("🚪 You have been logged out. Please navigate back to the login screen.")
        st.stop()

def render_sidebar():
    # 🌟 Aggressive CSS to completely nuke Streamlit's native sidebar nav
    st.markdown(
        """
        <style>
            section[data-testid="stSidebar"] nav {
                display: none !important;
                visibility: hidden !important;
            }
            div[data-testid="stSidebarNav"] {
                display: none !important;
                visibility: hidden !important;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )
    
    # 🔒 Strict Role Validation (Now perfectly matching your MongoDB)
    role = str(st.session_state.get("role", "")).lower()
    
    # If the role is NOT explicitly 'admin' or 'customer', kick them out safely
    if role not in ["admin", "customer"]:
        perform_logout()
        st.stop() # Halt execution so the rest of the UI doesn't try to render

    # 🎨 Build the Custom Sidebar
    with st.sidebar:
        try:
            render_logo(width=130)
        except Exception:
            pass 
            
        user_name = st.session_state.get("user_name", "Unknown")
        
        st.write(f"👤 User: **{user_name}**")
        
        st.page_link("Home.py", label="🏠 Home")
        
        # ⚙️ Admin View (Strictly Monitoring & CRM)
        if role == "admin":
            st.markdown("---")
            st.markdown("### ⚙️ Admin Tools")
            st.page_link("pages/3_Monitoring.py", label="📊 Monitoring")
            st.page_link("pages/2_Tickets.py", label="🎫 CRM Tickets")
        
        # 💬 Customer View (Strictly Chat)
        elif role == "customer":
            st.markdown("---")
            st.markdown("### 💬 User Tools")
            st.page_link("pages/1_chat.py", label="💬 Chat Agent")
        
        st.markdown("---")
        
        # 🚪 Sign Out Button
        st.button(
            "🚪 Sign out", 
            key=f"signout_{uuid.uuid4().hex[:8]}", 
            on_click=perform_logout, 
            use_container_width=True
        )