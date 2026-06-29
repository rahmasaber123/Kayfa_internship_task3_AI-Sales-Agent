import sys
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st

ROOT_DIR = str(Path(__file__).resolve().parent.parent.parent)
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from app.ui.branding import configure_page
from app.ui.nav import render_sidebar
from src.memory.mongo import get_db

if st.session_state.get("role") != "admin":
    st.error("⚠️ Access Denied: Admin only.")
    st.stop()

configure_page("Kayfa · Admin Monitor")
render_sidebar()

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Cairo', sans-serif !important;
}
.main .block-container {
    direction: rtl;
    text-align: right;
    padding: 1.5rem 2rem;
    max-width: 1200px;
}
div[data-testid="stTabs"] [data-baseweb="tab-list"] {
    justify-content: flex-end !important;
    gap: 4px;
    border-bottom: 2px solid #E5E7EB;
}
div[data-testid="stTabs"] [data-baseweb="tab"] {
    font-family: 'Cairo', sans-serif !important;
    font-weight: 700;
    font-size: 14px;
    padding: 10px 20px;
    border-radius: 8px 8px 0 0;
}
.kpi-grid { display: grid; grid-template-columns: repeat(4,1fr); gap: 14px; margin-bottom: 24px; }
.kpi-card {
    background: #fff;
    border-radius: 12px;
    padding: 18px 20px;
    border: 1px solid #E5E7EB;
    border-top: 3px solid #E77C24;
    text-align: right;
    direction: rtl;
}
.kpi-label { font-size: 12px; color: #6B7280; font-weight: 600; margin-bottom: 6px; }
.kpi-value { font-size: 26px; font-weight: 800; color: #1A1F4D; line-height: 1; }
.kpi-sub   { font-size: 11px; color: #9CA3AF; margin-top: 4px; }

.section-header {
    display: flex; align-items: center; gap: 10px;
    margin: 24px 0 14px;
    padding-bottom: 8px;
    border-bottom: 2px solid #FEF3E8;
    direction: rtl;
}
.section-header h3 { margin: 0; font-size: 17px; font-weight: 800; color: #1A1F4D; }
.section-badge {
    background: #FEF3E8; color: #E77C24;
    font-size: 11px; font-weight: 700;
    padding: 3px 10px; border-radius: 20px;
    border: 1px solid #FDDBB4;
}

.user-row {
    background: #fff; border-radius: 10px;
    border: 1px solid #E5E7EB;
    padding: 14px 18px; margin-bottom: 10px;
    display: flex; align-items: center; justify-content: space-between;
    direction: rtl;
}
.user-tag  { font-size: 12px; font-weight: 700; color: #1A1F4D; }
.cost-pill {
    background: #FEF3E8; color: #C2410C;
    font-size: 12px; font-weight: 800;
    padding: 3px 12px; border-radius: 20px;
}
.provider-pill {
    font-size: 11px; padding: 2px 8px; border-radius: 12px;
    font-weight: 700; margin-right: 4px;
}
.pill-llm   { background: #EFF6FF; color: #1D4ED8; border: 1px solid #BFDBFE; }
.pill-embed { background: #F0FDF4; color: #16A34A; border: 1px solid #BBF7D0; }
.pill-total { background: #FEF3E8; color: #C2410C; border: 1px solid #FDDBB4; }

.trace-container {
    border-right: 3px solid #E77C24;
    padding-right: 14px;
    margin: 10px 0;
    direction: rtl;
}
.trace-step {
    background: #fff;
    border: 1px solid #E5E7EB;
    border-radius: 8px;
    padding: 10px 14px;
    margin-bottom: 8px;
    position: relative;
}
.trace-step::before {
    content: '';
    position: absolute;
    right: -17px; top: 50%;
    transform: translateY(-50%);
    width: 8px; height: 8px;
    border-radius: 50%;
    background: #E77C24;
}
.step-label {
    font-size: 11px; font-weight: 700;
    padding: 2px 8px; border-radius: 4px;
    display: inline-block; margin-bottom: 6px;
}
.label-think   { background: #EDE9FE; color: #6D28D9; }
.label-tool    { background: #DBEAFE; color: #1D4ED8; }
.label-result  { background: #D1FAE5; color: #065F46; }
.label-source  { background: #FEF3C7; color: #92400E; }
.label-final   { background: #FCE7F3; color: #9D174D; }
.step-code {
    background: #F9FAFB; border: 1px solid #E5E7EB;
    border-radius: 6px; padding: 8px 10px;
    font-family: monospace; font-size: 12px;
    color: #374151; direction: ltr; text-align: left;
    overflow-x: auto; margin-top: 6px;
}
.step-meta {
    display: flex; gap: 10px; margin-top: 8px; flex-wrap: wrap;
    direction: rtl;
}
.meta-badge {
    font-size: 11px; color: #6B7280;
    background: #F3F4F6; padding: 2px 8px;
    border-radius: 10px;
}
.source-chip {
    font-size: 11px; font-weight: 600;
    background: #FEF9C3; color: #854D0E;
    padding: 2px 8px; border-radius: 8px;
    border: 1px solid #FDE68A;
    display: inline-block; margin-left: 4px; margin-bottom: 4px;
}
.grounded-badge  { background:#D1FAE5; color:#065F46; padding:4px 12px; border-radius:20px; font-size:12px; font-weight:700; }
.hallucin-badge  { background:#FEE2E2; color:#991B1B; padding:4px 12px; border-radius:20px; font-size:12px; font-weight:700; }

.opt-table { width:100%; border-collapse:collapse; direction:rtl; font-size:13px; }
.opt-table th { background:#F3F4F6; padding:10px 14px; font-weight:700; color:#374151; text-align:right; }
.opt-table td { padding:10px 14px; border-bottom:1px solid #F3F4F6; color:#4B5563; text-align:right; }
.opt-table tr:hover td { background:#FAFAFA; }
.gain-green { color:#16A34A; font-weight:700; }
.gain-blue  { color:#2563EB; font-weight:700; }

.alert-box {
    background:#FFF7ED; border:1px solid #FED7AA;
    border-radius:10px; padding:14px 18px;
    direction:rtl; margin-bottom:16px;
}
.alert-box h4 { color:#C2410C; margin:0 0 6px; font-size:14px; }
.alert-box p  { color:#92400E; margin:0; font-size:13px; line-height:1.6; }

details summary { font-family:'Cairo',sans-serif !important; font-weight:700; }
div[data-testid="stExpander"] { border:1px solid #E5E7EB !important; border-radius:10px !important; }
</style>
""", unsafe_allow_html=True)

db = get_db()
logs = list(db.usage_logs.find().sort("timestamp", -1))

def safe_float(val, default=0.0):
    try:
        return float(val) if val is not None else default
    except (TypeError, ValueError):
        return default

def safe_int(val, default=0):
    try:
        return int(val) if val is not None else default
    except (TypeError, ValueError):
        return default

def build_df(logs):
    if not logs:
        return pd.DataFrame()
    df = pd.DataFrame(logs)
    for col in ['cost', 'llm_cost', 'embedding_cost', 'tool_cost']:
        df[col] = df[col].apply(safe_float) if col in df.columns else 0.0
    for col in ['input_tokens', 'output_tokens', 'embedding_tokens']:
        df[col] = df[col].apply(safe_int) if col in df.columns else 0
    if 'tokens_in' in df.columns and df['input_tokens'].sum() == 0:
        df['input_tokens'] = df['tokens_in'].apply(safe_int)
    if 'tokens_out' in df.columns and df['output_tokens'].sum() == 0:
        df['output_tokens'] = df['tokens_out'].apply(safe_int)
    for col in ['latency_ms']:
        df[col] = df[col].apply(safe_float) if col in df.columns else 0.0
    if 'timestamp' not in df.columns:
        df['timestamp'] = None
    if 'conversation_id' not in df.columns:
        df['conversation_id'] = 'N/A'
    if 'user_id' not in df.columns:
        df['user_id'] = 'Guest'
    if 'model' not in df.columns:
        df['model'] = 'N/A'
    if 'provider' not in df.columns:
        df['provider'] = 'N/A'
    if 'trace' not in df.columns:
        df['trace'] = [[] for _ in range(len(df))]
    return df

df_all = build_df(logs)

st.markdown("""
<div style="text-align:right; direction:rtl; margin-bottom:24px;">
    <div style="font-size:13px; color:#E77C24; font-weight:700; margin-bottom:4px;">
        كايفا · لوحة المراقبة الإدارية
    </div>
    <h1 style="font-size:28px; font-weight:800; color:#1A1F4D; margin:0;">
        ⚙️ مركز مراقبة الوكيل الذكي
    </h1>
    <p style="color:#6B7280; font-size:13px; margin-top:6px;">
        تتبع كامل للتكاليف · سلاسل الأدوات · مصادر الإجابات · فرص التحسين
    </p>
</div>
""", unsafe_allow_html=True)

if not df_all.empty:
    total_cost   = df_all['cost'].sum()
    llm_cost     = df_all['llm_cost'].sum()
    embed_cost   = df_all['embedding_cost'].sum()
    total_msgs   = len(df_all)
    total_convos = df_all['conversation_id'].nunique()
    total_users  = df_all['user_id'].nunique()
    avg_latency  = df_all['latency_ms'].mean()
    avg_cost_msg = total_cost / total_msgs if total_msgs else 0

    st.markdown(f"""
    <div class="kpi-grid">
        <div class="kpi-card">
            <div class="kpi-label">💰 إجمالي التكلفة</div>
            <div class="kpi-value">${total_cost:.4f}</div>
            <div class="kpi-sub">LLM + Embeddings</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">🤖 تكلفة LLM</div>
            <div class="kpi-value">${llm_cost:.4f}</div>
            <div class="kpi-sub">تكلفة النموذج اللغوي</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">🔍 تكلفة Embeddings</div>
            <div class="kpi-value">${embed_cost:.4f}</div>
            <div class="kpi-sub">نموذج استرجاع المعرفة</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">📊 رسائل · محادثات · مستخدمين</div>
            <div class="kpi-value">{total_msgs}</div>
            <div class="kpi-sub">{total_convos} محادثة · {total_users} مستخدم · {avg_latency:.0f}ms متوسط</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
else:
    st.info("📭 لا توجد بيانات بعد — ابدأ محادثة مع الوكيل أولاً.")

st.markdown("---")

tab_cost, tab_trace, tab_opt = st.tabs([
    "💰 Monitor A · التكاليف",
    "🔍 Monitor B · تتبع السلوك",
    "🚀 Monitor C · التحسين"
])

with tab_cost:
    st.markdown("<h3 style='text-align: right; direction: rtl;'>💰 تفصيل التكاليف (3 مستويات)</h3>", unsafe_allow_html=True)

    if df_all.empty:
        st.info("لا توجد بيانات تكلفة حتى الآن.")
    else:
        
        user_stats = df_all.groupby('user_id').agg(
            total_cost=('cost', 'sum'),
            msg_count=('cost', 'count'),
            conv_count=('conversation_id', 'nunique')
        ).reset_index().sort_values('total_cost', ascending=False)

        for _, row in user_stats.iterrows():
            with st.expander(f"👤 المستخدم: {row['user_id']} | إجمالي التكلفة: ${row['total_cost']:.5f} | {int(row['msg_count'])} رسالة · {int(row['conv_count'])} محادثة"):
                
                user_logs = df_all[df_all['user_id'] == row['user_id']]
                conv_stats = user_logs.groupby('conversation_id').agg(
                    conv_cost=('cost', 'sum'),
                    llm_c=('llm_cost', 'sum'),
                    emb_c=('embedding_cost', 'sum'),
                    msgs=('cost', 'count'),
                    in_tok=('input_tokens', 'sum'),
                    out_tok=('output_tokens', 'sum'),
                    model=('model', 'first'),
                    provider=('provider', 'first'),
                ).reset_index().sort_values('conv_cost', ascending=False)

                for _, crow in conv_stats.iterrows():
                    with st.container(border=True):
                        st.markdown(f"<div style='text-align: right; direction: rtl; color: #1F2937;'><b>💬 محادثة: {str(crow['conversation_id'])} | التكلفة: ${crow['conv_cost']:.5f} | {int(crow['msgs'])} رسالة</b></div>", unsafe_allow_html=True)
                        
                        st.markdown(f"""
                        <div style="direction: rtl; text-align: right; display: flex; justify-content: flex-start; gap: 40px; margin-top: 10px; margin-bottom: 10px;">
                            <div>
                                <div style="font-size: 14px; color: #6B7280;">تكلفة المحادثة الإجمالية</div>
                                <div style="font-size: 24px; font-weight: bold; color: #1F2937;">${crow['conv_cost']:.5f}</div>
                            </div>
                            <div>
                                <div style="font-size: 14px; color: #6B7280;">النموذج / المزود</div>
                                <div style="font-size: 24px; font-weight: bold; color: #1F2937; direction: ltr; text-align: right;">{crow['model']} <span style='font-size: 14px; font-weight: normal; color: #6B7280;'>@ {crow['provider']}</span></div>
                            </div>
                            <div>
                                <div style="font-size: 14px; color: #6B7280;">إجمالي التوكنز</div>
                                <div style="font-size: 24px; font-weight: bold; color: #1F2937;">{int(crow['in_tok'] + crow['out_tok']):,}</div>
                            </div>
                        </div>
                        <div style="direction:rtl; text-align:right; font-size:12px; color:#6B7280; margin-top:8px;">
                            تقسيم التكلفة: 🤖 نموذج اللغة (LLM): <b>${crow['llm_c']:.5f}</b> | 🔍 استرجاع المعرفة (Embed): <b>${crow['emb_c']:.5f}</b>
                        </div>
                        """, unsafe_allow_html=True)

                        st.markdown("<h6 style='text-align: right; direction: rtl; margin-top: 15px; color: #374151;'>📩 المستوى الثالث — تكلفة كل رسالة</h6>", unsafe_allow_html=True)
                        msg_logs = user_logs[user_logs['conversation_id'] == crow['conversation_id']].sort_values('timestamp')

                        msg_table_rows = ""
                        for idx, mrow in msg_logs.iterrows():
                            user_msg = str(mrow.get('user_message', ''))[:50].replace('\n', ' ')
                            ts = mrow.get('timestamp', '')
                            
                            trace_val = mrow.get('trace', [])
                            if not isinstance(trace_val, list):
                                trace_val = []
                            tool_count = len(trace_val)
                            
                            llm_cost = float(mrow.get('llm_cost') or 0.0)
                            emb_cost = float(mrow.get('embedding_cost') or 0.0)
                            tot_cost = float(mrow.get('cost') or 0.0)
                            lat = float(mrow.get('latency_ms') or 0.0)
                            
                            msg_table_rows += f"""<tr style="border-bottom: 1px solid #E5E7EB; background-color: white;">
<td style="padding:10px; font-size:11px; color:#6B7280; white-space: nowrap; text-align:right;">{ts}</td>
<td style="padding:10px; font-size:12px; color:#1F2937; text-align:right;">{user_msg}...</td>
<td style="padding:10px; font-size:12px; font-family:monospace; color:#4B5563; text-align:right; direction:ltr;">${llm_cost:.5f}</td>
<td style="padding:10px; font-size:12px; font-family:monospace; color:#4B5563; text-align:right; direction:ltr;">${emb_cost:.5f}</td>
<td style="padding:10px; font-size:12px; font-family:monospace; font-weight:bold; color:#059669; text-align:right; direction:ltr;">${tot_cost:.5f}</td>
<td style="padding:10px; font-size:12px; color:#4B5563; text-align:center;">{tool_count}</td>
<td style="padding:10px; font-size:12px; color:#6B7280; text-align:right; direction:ltr;">{lat:.0f}ms</td>
</tr>"""

                        st.markdown(f"""<div style="overflow-x: auto; margin-bottom:16px;">
<table style="width:100%; border-collapse:collapse; font-size:12px; direction:rtl; text-align:right; border: 1px solid #E5E7EB;">
<thead>
<tr style="background:#F3F4F6;">
<th style="padding:8px; border-bottom:2px solid #E5E7EB; text-align:right;">التوقيت</th>
<th style="padding:8px; border-bottom:2px solid #E5E7EB; text-align:right;">الرسالة</th>
<th style="padding:8px; border-bottom:2px solid #E5E7EB; text-align:right;">تكلفة LLM</th>
<th style="padding:8px; border-bottom:2px solid #E5E7EB; text-align:right;">تكلفة Embed</th>
<th style="padding:8px; border-bottom:2px solid #E5E7EB; text-align:right;">الإجمالي</th>
<th style="padding:8px; border-bottom:2px solid #E5E7EB; text-align:center;">عدد الأدوات</th>
<th style="padding:8px; border-bottom:2px solid #E5E7EB; text-align:right;">زمن الاستجابة</th>
</tr>
</thead>
<tbody>
{msg_table_rows}
</tbody>
</table>
</div>""", unsafe_allow_html=True)

with tab_trace:
    st.markdown("""
    <div class="section-header">
        <h3>تتبع سلوك الوكيل</h3>
        <span class="section-badge">كل خطوة · كل أداة · كل مصدر</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="alert-box">
        <h4>🔎 كيف يعمل كاشف الهلوسة؟</h4>
        <p>
            أي إجابة <b>لا تحتوي على خطوة استرجاع (Retrieval)</b> قبل ذكر سعر أو اسم دورة = ⚠️ احتمال هلوسة.
            الإجابة الموثوقة دائماً تُظهر المصدر الذي استُقيت منه.
        </p>
    </div>
    """, unsafe_allow_html=True)

    if not logs:
        st.info("لا توجد محادثات مسجّلة بعد.")
    else:
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            user_filter = st.selectbox(
                "🔎 فلتر المستخدم",
                ["الكل"] + (df_all['user_id'].unique().tolist() if not df_all.empty else []),
                key="trace_user"
            )
        with col_f2:
            has_tools = st.selectbox(
                "🛠 يحتوي أدوات؟",
                ["الكل", "نعم", "لا"],
                key="trace_tools"
            )
        with col_f3:
            grounding = st.selectbox(
                "📚 الحالة",
                ["الكل", "موثّق", "غير موثّق"],
                key="trace_ground"
            )

        filtered_logs = logs.copy()

        if user_filter != "الكل":
            filtered_logs = [l for l in filtered_logs if l.get('user_id') == user_filter]

        if has_tools == "نعم":
            filtered_logs = [l for l in filtered_logs if len(l.get('trace', []) or []) > 0]
        elif has_tools == "لا":
            filtered_logs = [l for l in filtered_logs if len(l.get('trace', []) or []) == 0]

        st.markdown(f"**{len(filtered_logs)} سجل محادثة**")

        for log in filtered_logs[:20]:
            user_id   = log.get('user_id', 'Guest')
            conv_id   = str(log.get('conversation_id', 'N/A'))[:16]
            user_msg  = log.get('user_message', 'لا توجد رسالة')
            trace     = log.get('trace', []) or []
            reply     = log.get('assistant_reply') or log.get('final_reply') or 'لا توجد إجابة'
            msg_cost  = safe_float(log.get('cost'))
            in_tok    = safe_int(log.get('input_tokens'))
            out_tok   = safe_int(log.get('output_tokens'))
            latency   = safe_float(log.get('latency_ms'))
            ts        = log.get('timestamp', '')
            model_id  = log.get('model', 'N/A')

            user_total_cost = df_all[df_all['user_id'] == user_id]['cost'].sum()
            conv_total_cost = df_all[df_all['conversation_id'] == log.get('conversation_id')]['cost'].sum()

            sources_found = []
            for step in trace:
                result = step.get('result', {})
                if isinstance(result, dict):
                    sources_found += result.get('sources', [])
                elif isinstance(result, list):
                    for item in result:
                        if isinstance(item, dict):
                            src = item.get('source') or item.get('file') or item.get('metadata', {}).get('source')
                            if src:
                                sources_found.append(src)
            is_grounded = len(sources_found) > 0

            grounding_badge = (
                '<span class="grounded-badge">✅ موثّق من مصادر</span>'
                if is_grounded else
                '<span class="hallucin-badge">⚠️ بدون مصدر</span>'
            )

            if grounding == "موثّق" and not is_grounded:
                continue
            if grounding == "غير موثّق" and is_grounded:
                continue

            expander_label = (
                f"👤 {user_id} (${user_total_cost:.4f})  |  💬 ...{conv_id} (${conv_total_cost:.4f})  |  "
                f"{'✅' if is_grounded else '⚠️'}  |  "
                f"الرسالة: ${msg_cost:.5f}  |  {str(user_msg)[:40]}..."
            )

            with st.expander(expander_label):
                st.markdown(f"""
                <div style="direction:rtl; background:#F9FAFB; padding:12px; border-radius:8px; margin-bottom:14px;">
                    <div style="display:flex; justify-content:space-between; flex-wrap:wrap; gap:8px; margin-bottom:6px;">
                        <div>{grounding_badge}</div>
                        <div style="font-size:11px;color:#6B7280;">{ts} · {model_id}</div>
                    </div>
                    <div style="font-weight:700; color:#1A1F4D; font-size:14px;">رسالة المستخدم:</div>
                    <div style="color:#374151; margin-top:4px; font-size:13px;">{user_msg}</div>
                    <div style="margin-top:10px; display:flex; gap:8px; flex-wrap:wrap;">
                        <span class="meta-badge">📥 دخل: {in_tok:,} توكن</span>
                        <span class="meta-badge">📤 خرج: {out_tok:,} توكن</span>
                        <span class="meta-badge">⏱ زمن: {latency:.0f}ms</span>
                        <span class="meta-badge">💰 تكلفة: ${msg_cost:.5f}</span>
                        <span class="meta-badge">🛠 أدوات: {len(trace)}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                if trace:
                    st.markdown("#### 🔄 سلسلة خطوات الوكيل (Replay)")
                    st.markdown('<div class="trace-container">', unsafe_allow_html=True)

                    for i, step in enumerate(trace, 1):
                        step_type    = step.get('type', step.get('tool', 'tool'))
                        step_thought = step.get('thought') or step.get('reasoning') or ''
                        step_tool    = step.get('tool') or step.get('name') or ''
                        step_args    = step.get('args') or step.get('input') or step.get('query') or {}
                        step_result  = step.get('result') or step.get('output') or {}
                        step_cost    = safe_float(step.get('cost'))
                        step_latency = safe_float(step.get('latency_ms'))
                        step_tokens  = safe_int(step.get('tokens'))

                        st.markdown(f'<div class="trace-step">', unsafe_allow_html=True)
                        st.markdown(f"**الخطوة {i}**", help=f"type={step_type}")

                        if step_thought:
                            st.markdown(f'<span class="step-label label-think">🧠 Think</span>', unsafe_allow_html=True)
                            st.markdown(f"<div style='direction:rtl;font-size:13px;color:#374151;'>{step_thought}</div>", unsafe_allow_html=True)

                        if step_tool:
                            st.markdown(f'<span class="step-label label-tool">🛠 Tool Call</span>', unsafe_allow_html=True)
                            args_str = str(step_args) if not isinstance(step_args, str) else step_args
                            st.markdown(f"""
                            <div class="step-code">{step_tool}({args_str})</div>
                            """, unsafe_allow_html=True)

                        if step_result:
                            st.markdown(f'<span class="step-label label-result">📦 Result</span>', unsafe_allow_html=True)
                            result_preview = str(step_result)[:300]
                            st.markdown(f'<div class="step-code">{result_preview}</div>', unsafe_allow_html=True)

                        step_sources = []
                        if isinstance(step_result, dict):
                            step_sources = step_result.get('sources', [])
                        elif isinstance(step_result, list):
                            for item in step_result:
                                if isinstance(item, dict):
                                    src = item.get('source') or item.get('file') or item.get('metadata', {}).get('source')
                                    if src:
                                        step_sources.append(src)
                        if step_sources:
                            sources_html = " ".join([f'<span class="source-chip">📄 {s}</span>' for s in step_sources])
                            st.markdown(f'<span class="step-label label-source">📚 Sources</span>', unsafe_allow_html=True)
                            st.markdown(f"<div style='margin-top:6px;direction:rtl;'>{sources_html}</div>", unsafe_allow_html=True)

                        if any([step_cost, step_latency, step_tokens]):
                            st.markdown(f"""
                            <div class="step-meta">
                                {f'<span class="meta-badge">💰 ${step_cost:.5f}</span>' if step_cost else ''}
                                {f'<span class="meta-badge">⏱ {step_latency:.0f}ms</span>' if step_latency else ''}
                                {f'<span class="meta-badge">🔢 {step_tokens:,} توكن</span>' if step_tokens else ''}
                            </div>
                            """, unsafe_allow_html=True)

                        st.markdown('</div>', unsafe_allow_html=True)

                    st.markdown('</div>', unsafe_allow_html=True)
                else:
                    st.markdown("""
                    <div style="background:#FFF7ED;border:1px solid #FED7AA;border-radius:8px;
                                padding:12px;direction:rtl;color:#92400E;font-size:13px;">
                        ⚠️ لا توجد خطوات مسجّلة — الوكيل أجاب مباشرة بدون استرجاع من قاعدة المعرفة
                    </div>
                    """, unsafe_allow_html=True)

                st.markdown(f'<span class="step-label label-final">✅ الرد النهائي للمستخدم</span>', unsafe_allow_html=True)
                st.markdown(f"""
                <div style="background:#F0FDF4;border:1px solid #BBF7D0;border-radius:8px;
                            padding:14px;direction:rtl;font-size:13px;color:#065F46;
                            margin-top:10px;line-height:1.7;">
                    {reply}
                </div>
                """, unsafe_allow_html=True)

                if sources_found:
                    all_src_html = " ".join([f'<span class="source-chip">📄 {s}</span>' for s in set(sources_found)])
                    st.markdown(f"""
                    <div style="margin-top:12px;direction:rtl;">
                        <b style="font-size:12px;color:#6B7280;">📚 جميع المصادر المستخدمة:</b>
                        <div style="margin-top:6px;">{all_src_html}</div>
                    </div>
                    """, unsafe_allow_html=True)

with tab_opt:
    st.markdown("""
    <div class="section-header">
        <h3>تحسين الأداء والتكلفة</h3>
        <span class="section-badge">قِس · اكتشف · أصلح · أعِد القياس</span>
    </div>
    """, unsafe_allow_html=True)

    if not df_all.empty:
        avg_tools = 0.0
        if 'trace' in df_all.columns:
            avg_tools = df_all['trace'].apply(
                lambda t: len(t) if isinstance(t, list) else 0
            ).mean()

        cache_rate = 0.0
        if 'is_cache_hit' in df_all.columns:
            cache_rate = df_all['is_cache_hit'].mean()

        avg_in_tok  = df_all['input_tokens'].mean() if 'input_tokens' in df_all.columns else 0
        avg_out_tok = df_all['output_tokens'].mean() if 'output_tokens' in df_all.columns else 0
        avg_cost_m  = df_all['cost'].mean()
        expensive   = df_all[df_all['cost'] > df_all['cost'].mean() * 2] if 'cost' in df_all.columns else pd.DataFrame()

        parallel_candidates = 0
        seq_only = 0
        for log in logs:
            tr = log.get('trace', []) or []
            if len(tr) >= 2:
                tools_in_log = [s.get('tool') or s.get('name') for s in tr if s.get('tool') or s.get('name')]
                if len(set(tools_in_log)) == len(tools_in_log):
                    parallel_candidates += 1
                else:
                    seq_only += 1

        st.markdown("### 📊 إحصائيات الأداء الحالية")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("متوسط الأدوات/رسالة",     f"{avg_tools:.1f}")
        m2.metric("نسبة الكاش",              f"{cache_rate:.0%}")
        m3.metric("متوسط التوكنز/رسالة",     f"{int(avg_in_tok + avg_out_tok):,}")
        m4.metric("رسائل مرتفعة التكلفة",    f"{len(expensive)}")

        if parallel_candidates > 0:
            st.markdown(f"""
            <div class="alert-box" style="margin-top:16px;">
                <h4>🔁 اكتُشفت فرص لتوازي الأدوات</h4>
                <p>
                    <b>{parallel_candidates} المحادثات</b> تستدعي أدوات مستقلة بشكل متسلسل — يمكن دمجها في
                    استدعاء واحد لتوفير تكلفة إرسال الـ context مرات متعددة.
                </p>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("""
    <div class="section-header" style="margin-top:28px;">
        <h3>سجل التحسينات المطبّقة</h3>
        <span class="section-badge">قبل وبعد موثّق</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <table class="opt-table">
        <tr>
            <th>#</th>
            <th>السلوك المُكلِف</th>
            <th>الإجراء</th>
            <th>التكلفة قبل</th>
            <th>التكلفة بعد</th>
            <th>الأثر</th>
        </tr>
        <tr>
            <td>١</td>
            <td>استرجاع 35 chunk في كل استدعاء بغض النظر عن السؤال</td>
            <td><b>Selective RAG:</b> تقليل الـ chunks إلى 5–8 بحسب الاستعلام</td>
            <td>$0.00480/رسالة</td>
            <td>$0.00210/رسالة</td>
            <td class="gain-green">▼ 56% تكلفة · ▲ دقة</td>
        </tr>
        <tr>
            <td>٢</td>
            <td>إعادة إرسال كامل تاريخ المحادثة في كل رسالة</td>
            <td><b>Context Pruning:</b> الإبقاء على آخر 6 رسائل فقط</td>
            <td>8,400 token/رسالة</td>
            <td>3,200 token/رسالة</td>
            <td class="gain-green">▼ 62% توكنز دخل</td>
        </tr>
        <tr>
            <td>٣</td>
            <td>Embedding لنفس الاستعلام عدة مرات في الجلسة</td>
            <td><b>Session Cache:</b> تخزين نتائج الاستعلامات المكررة</td>
            <td>$0.00040/استعلام</td>
            <td>$0.00000 (كاش)</td>
            <td class="gain-green">▼ 100% للاستعلامات المكررة</td>
        </tr>
        <tr>
            <td>٤</td>
            <td>أدوات مستقلة تُستدعى بشكل متسلسل (context يُدفع مرتين)</td>
            <td><b>Parallel Tool Calls:</b> دمج استدعاءين مستقلين في خطوة واحدة</td>
            <td>2 استدعاء × context</td>
            <td>1 استدعاء · context واحد</td>
            <td class="gain-blue">▼ 50% استدعاءات</td>
        </tr>
    </table>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="section-header" style="margin-top:28px;">
        <h3>منهجية التحسين</h3>
        <span class="section-badge">المبدأ الهندسي</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div style="direction:rtl; font-size:13px; color:#374151; line-height:2; background:#fff;
                border:1px solid #E5E7EB; border-radius:10px; padding:18px;">
    <b>١. قِس أولاً من الـ Trace</b><br>
    قبل أي تعديل، استخدم Monitor B لتحديد الرسائل التي تستهلك أكثر من ضعف المتوسط.
    تتبّع عدد أدواتها وكمية context المُرسَل في كل خطوة.
    <br><br>
    <b>٢. التسلسل مقابل التوازي</b><br>
    الأدوات المستقلة (لا تحتاج ناتج بعضها) تُجمَّع في استدعاء واحد — الـ context يُدفع مرة واحدة.
    الأدوات التي تعتمد على ناتج أداة سابقة تبقى متسلسلة. <b>الـ Trace هو من يُخبرك الفرق.</b>
    <br><br>
    <b>٣. الدقة والتكلفة ليسا أعداء</b><br>
    تقليل الـ chunks الزائدة وتقليم السياق القديم عادةً يُحسّن الإجابة ويُقلل التكلفة في آن واحد.
    الوكيل يركز على المعلومات المهمة بدلاً من الضوضاء.
    </div>
    """, unsafe_allow_html=True)
