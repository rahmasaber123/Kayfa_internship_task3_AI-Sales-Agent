import sys
from pathlib import Path
import pandas as pd
import streamlit as st

# ─────────────────────────────────────────────────────────────────────
# Setup Path & Imports
# ─────────────────────────────────────────────────────────────────────
ROOT_DIR = str(Path(__file__).resolve().parent.parent.parent)
if ROOT_DIR not in sys.path: sys.path.append(ROOT_DIR)

from app.ui.branding import configure_page
from app.ui.nav import render_sidebar
from src.memory.mongo import get_db

# Security Check
if st.session_state.get("role") != "admin":
    st.error("⚠️ Access Denied: Admin only.")
    st.stop()

configure_page("Kayfa · Admin Monitor")
render_sidebar()

# ─────────────────────────────────────────────────────────────────────
# Modern UI Component: Trace Card
# ─────────────────────────────────────────────────────────────────────
def render_trace_card(log_entry):
    timestamp = log_entry.get("timestamp", "N/A")
    user = log_entry.get("user_id", "Guest")
    user_msg = log_entry.get("user_message", "No message")
    trace = log_entry.get("trace", [])
    reply = log_entry.get("assistant_reply", log_entry.get("final_reply", "No response"))
    msg_cost = log_entry.get("cost", 0.0)

    with st.expander(f"👤 {user} | 💰 ${float(msg_cost):.5f} | {user_msg[:40]}..."):
        st.markdown(f"**الرسالة:** {user_msg}")
        st.markdown(f"**إجمالي تكلفة الرسالة:** `${float(msg_cost):.6f}`")
        st.markdown("#### 🛠 عمليات الـ Agent (Tool Chain)")
        if trace:
            for step in trace:
                tool_name = step.get("tool", "Tool Call")
                step_cost = step.get("cost", 0.0)
                st.markdown(f"""
                <div style="border-right: 3px solid #E77C24; padding-right: 10px; background: #fff7ed; padding: 8px; border-radius: 4px; margin-bottom: 8px;">
                    <div style="display: flex; justify-content: space-between;">
                        <code style="color: #c2410c; font-weight: bold;">{tool_name}</code>
                        <span style="font-size: 11px; font-weight: bold;">Cost: ${float(step_cost):.6f}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        st.success(reply)

# ─────────────────────────────────────────────────────────────────────
# Styles (Force Tabs to Right & Cleaner UI)
# ─────────────────────────────────────────────────────────────────────
st.markdown("""
    <style>
    /* Tabs Alignment */
    div[data-testid="stTabs"] [data-baseweb="tab-list"] { justify-content: flex-end !important; }
    
    .card { background: #FFFFFF; border-radius: 12px; padding: 20px; border: 1px solid #E5E7EB; margin-bottom: 20px; direction: rtl; text-align: right; }
    .metric-title { font-size: 13px; color: #6B7280; font-weight: 600; margin-bottom: 5px; }
    .metric-value { font-size: 28px; font-weight: 800; color: #1A1F4D; }
    div[data-testid="stMarkdownContainer"] { direction: rtl; text-align: right; }
    </style>
""", unsafe_allow_html=True)

st.title("⚙️ لوحة المراقبة المركزية")
st.markdown("---")

# ─────────────────────────────────────────────────────────────────────
# Data Fetching & Robust Initialization
# ─────────────────────────────────────────────────────────────────────
db = get_db()
logs = list(db.usage_logs.find().sort("timestamp", -1))
df_all = pd.DataFrame(logs) if logs else pd.DataFrame()

def safe_init_col(df, col_name):
    if col_name not in df.columns: df[col_name] = 0.0
    else: df[col_name] = pd.to_numeric(df[col_name], errors='coerce').fillna(0.0)
    return df

if not df_all.empty:
    df_all = safe_init_col(df_all, 'cost')
    df_all = safe_init_col(df_all, 'llm_cost')
    df_all = safe_init_col(df_all, 'embedding_cost')
    df_all = safe_init_col(df_all, 'tool_cost')
    
    cost_stats = df_all.groupby(['user_id']).agg({
        'cost': 'sum', 'llm_cost': 'sum', 'embedding_cost': 'sum', 'tool_cost': 'sum'
    }).reset_index()
else:
    cost_stats = pd.DataFrame()

# ─────────────────────────────────────────────────────────────────────
# Tabs
# ─────────────────────────────────────────────────────────────────────
tab3, tab2, tab1 = st.tabs(["🚀 Monitor C: Opt", "🔍 Monitor B: Trace", "💰 Monitor A: Cost"])

with tab1:
    if df_all.empty: 
        st.info("لا توجد بيانات تكلفة.")
    else:
        kpi1, kpi2, kpi3 = st.columns(3)
        kpi1.metric("إجمالي المصروفات", f"${df_all['cost'].sum():.4f}")
        kpi2.metric("استهلاك الـ LLM", f"${df_all['llm_cost'].sum():.4f}")
        kpi3.metric("الرسائل النشطة", len(df_all))

        st.markdown("### 📋 سجل الحركات التفصيلي (User Logs)")
        
        # تحويل الجدول لـ Expanders لتحسين الـ UX
        for user in cost_stats['user_id'].unique():
            user_data = cost_stats[cost_stats['user_id'] == user]
            with st.expander(f"👤 مستخدم: {user} | الإجمالي: ${user_data['cost'].values[0]:.4f}"):
                c1, c2, c3 = st.columns(3)
                c1.write(f"**LLM:** ${user_data['llm_cost'].values[0]:.4f}")
                c2.write(f"**Embed:** ${user_data['embedding_cost'].values[0]:.4f}")
                c3.write(f"**Tools:** ${user_data['tool_cost'].values[0]:.4f}")

with tab2:
    if not logs: 
        st.info("لا توجد بيانات مراقبة.")
    else:
        st.subheader("إعادة تشغيل المحادثات (Step-Level Trace)")
        for log in logs[:15]:
            render_trace_card(log)

with tab3:
    st.subheader("تقارير تحسين الأداء")
    if not df_all.empty:
        col1, col2 = st.columns(2)
        avg_tools = df_all['trace'].apply(lambda t: len(t) if isinstance(t, list) else 0).mean() if 'trace' in df_all.columns else 0
        col2.metric("متوسط الأدوات/الرسالة", f"{avg_tools:.1f}")
        col1.metric("نسبة الكاش", f"{(df_all['is_cache_hit'].mean() if 'is_cache_hit' in df_all.columns else 0):.1%}")

    st.markdown("""
    <div class="card" style="margin-top: 20px;">
        <h4 style="color: #1A1F4D; margin-bottom: 15px; font-weight: bold;">🛠 سجل التحسينات الهندسية</h4>
        <table style="width: 100%; border-collapse: collapse; text-align: right; direction: rtl; font-size: 13px;">
            <tr style="background-color: #F3F4F6;"><th>الإجراء</th><th>الأثر</th></tr>
            <tr><td><b>RAG Retrieval:</b> 35 → 10 Chunks.</td><td style="color: green;">+40% Accuracy</td></tr>
            <tr><td><b>Query Cache:</b> Local Session caching.</td><td style="color: green;">$0 cost repeated.</td></tr>
            <tr><td><b>Context Pruning:</b> Last 6 msgs.</td><td style="color: green;">Stability.</td></tr>
        </table>
    </div>
    """, unsafe_allow_html=True)