import sys
import os
import re
from pathlib import Path
from datetime import datetime, timezone
import html as _html
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from collections import Counter

# 1. Force both the repo root and the app folder into the system path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
app_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))

if repo_root not in sys.path:
    sys.path.insert(0, repo_root)
if app_folder not in sys.path:
    sys.path.insert(0, app_folder)

import streamlit as st
from app.ui.branding import configure_page
from app.ui.nav import render_sidebar

# 2. إعداد الصفحة
configure_page("Kayfa · Tickets")

# 3. الحماية والأمان (Admin Only)
if not st.session_state.get("authenticated"):
    st.warning("Please sign in via the main page first.")
    st.stop()

if st.session_state.get("role") != "admin":
    st.error("⚠️ Access Denied: Admin only.")
    st.stop()

# 4. عرض القائمة الجانبية (ONLY CALLED ONCE)
render_sidebar()

# Initialize session states safely
if 'ticket_filter' not in st.session_state:
    st.session_state.ticket_filter = 'all'
if 'ticket_search' not in st.session_state:
    st.session_state.ticket_search = ''

@st.cache_resource(show_spinner="Connecting…")
def get_db():
    from src.memory.mongo import get_db as _get_db
    return _get_db()

db = get_db()

# ─────────────────────────────────────────────────────────────────────
# Data Validation Layer
# ─────────────────────────────────────────────────────────────────────
def validate_email(email: str) -> bool:
    if not email or email.strip() in ["—", ""]:
        return False
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email.strip()))

def validate_international_phone(phone: str) -> tuple[bool, str]:
    if not phone or phone.strip() in ["—", ""]:
        return False, "⚠️ رقم مفقود"
    
    clean_phone = "".join(c for c in phone if c.isdigit() or c == "+")
    
    if not (clean_phone.startswith("+") or clean_phone.startswith("00")):
        return False, "⚠️ بدون رمز دولي"
    
    if clean_phone.startswith("00"):
        clean_phone = "+" + clean_phone[2:]
        
    if clean_phone.startswith("+20"):
        if len(clean_phone) != 13:
            return False, "⚠️ رقم مصري غير دقيق"
    elif clean_phone.startswith("+966"):
        if len(clean_phone) != 13:
            return False, "⚠️ رقم سعودي غير دقيق"
    elif len(clean_phone) < 11 or len(clean_phone) > 15:
        return False, "⚠️ طول غير منطقي"
        
    return True, "✅ موثق دولياً"

# ─────────────────────────────────────────────────────────────────────
# Database KPIs (Robust to handle root or nested temperature)
# ─────────────────────────────────────────────────────────────────────
n_leads = db.tickets.count_documents({"type": "lead"})
n_esc   = db.tickets.count_documents({"type": "escalation"})
n_total = db.tickets.count_documents({})

# Updated queries to support both root 'temperature' and legacy 'lead_data.temperature'
hot   = db.tickets.count_documents({"type": "lead", "$or": [{"temperature": {"$regex": "^hot$", "$options": "i"}}, {"lead_data.temperature": {"$regex": "^hot$", "$options": "i"}}]})
warm  = db.tickets.count_documents({"type": "lead", "$or": [{"temperature": {"$regex": "^warm$", "$options": "i"}}, {"lead_data.temperature": {"$regex": "^warm$", "$options": "i"}}]})
cold  = db.tickets.count_documents({"type": "lead", "$or": [{"temperature": {"$regex": "^cold$", "$options": "i"}}, {"lead_data.temperature": {"$regex": "^cold$", "$options": "i"}}]})

undefined_temp = n_leads - (hot + warm + cold)
warm_display = warm + undefined_temp

# ─────────────────────────────────────────────────────────────────────
# Header (Pure RTL Arabic)
# ─────────────────────────────────────────────────────────────────────
st.markdown("<h1 style='text-align: right; direction: rtl;'>🎫 لوحة إدارة التذاكر و الـ CRM</h1>", unsafe_allow_html=True)
st.markdown(
    '<p style="color:#6B7280; margin-top:-10px; text-align: right; direction: rtl;">'
    'تذاكر العملاء المستخرجة بواسطة الذكاء الاصطناعي والتصعيدات البشرية الفورية. تظهر التذاكر الساخنة أولاً.</p>',
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────────────────────────────
# CRM Stats Columns
# ─────────────────────────────────────────────────────────────────────
st.markdown("<div dir='rtl'>", unsafe_allow_html=True)
f1, f2, f3, f4, f5 = st.columns(5)
_active = st.session_state.ticket_filter

def _btn(col, label, key, count, fval):
    active_style = "primary" if _active == fval else "secondary"
    with col:
        if st.button(f"{label}\n**{count}**", key=key,
                     use_container_width=True, type=active_style):
            st.session_state.ticket_filter = fval
            st.rerun()

_btn(f1, "📋 الكل",           "f_all",  n_total,       'all')
_btn(f2, "🔥 ساخن",           "f_hot",  hot,           'hot')
_btn(f3, "🔹 مهتم",           "f_warm", warm_display,  'warm')
_btn(f4, "❄️ بارد",           "f_cold", cold,          'cold')
_btn(f5, "⚠️ تصعيد",         "f_esc",  n_esc,         'escalation')
st.markdown("</div>", unsafe_allow_html=True)

# Search Input
st.markdown("<div dir='rtl' style='margin-top: 15px; margin-bottom: 15px;'>", unsafe_allow_html=True)
st.session_state.ticket_search = st.text_input(
    "", placeholder="🔍 ابحث بالاسم أو الهاتف أو البريد...",
    label_visibility="collapsed"
)
st.markdown("</div>", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────
def _fmt_time(ts) -> str:
    if not ts: return ""
    if isinstance(ts, str):
        try: ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception: return ts
    if not ts.tzinfo: ts = ts.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    d = (now - ts).total_seconds()
    if d < 60:    return "منذ ثوانٍ"
    if d < 3600:  return f"منذ {int(d/60)} دقيقة"
    if d < 86400: return f"منذ {int(d/3600)} ساعة"
    return ts.strftime("%b %d, %H:%M")

def _wa_link(phone: str) -> str:
    if not phone: return ""
    digits = "".join(c for c in phone if c.isdigit())
    return f"https://wa.me/{digits}" if digits else ""

def _esc(s) -> str:
    return _html.escape(str(s or "")).strip()

def _chip(text: str, color: str = "#E8ECFF", text_color: str = "#1A1F4D") -> str:
    return (f'<span style="display:inline-block; background:{color}; color:{text_color}; '
            f'padding:4px 12px; border-radius:12px; font-size:12px; margin:2px 0 2px 6px; '
            f'font-weight:600; direction:rtl;">{_esc(text)}</span>')

# ─────────────────────────────────────────────────────────────────────
# Renderers
# ─────────────────────────────────────────────────────────────────────
def render_lead_inner_body(t: dict) -> str:
    contact     = t.get("contact") or {}
    
    temp_val = t.get("temperature")
    if not temp_val and "lead_data" in t and isinstance(t["lead_data"], dict):
        temp_val = t["lead_data"].get("temperature")
    
    temp = str(temp_val or "warm").lower()

    ticket_id   = _esc(t.get("ticket_id", ""))
    name        = _esc(contact.get("name") or "زائر غير مسجل")
    phone       = _esc(contact.get("phone") or "")
    email       = _esc(contact.get("email") or "")
    city        = _esc(contact.get("city") or "")
    country     = _esc(contact.get("country") or "")
    channel     = _esc(contact.get("preferred_channel") or "واتساب")
    language    = _esc(t.get("language") or "عربي")
    dialect     = _esc(t.get("dialect") or "msa")
    products    = t.get("products_of_interest") or []
    goal        = _esc(t.get("goal") or "")
    level       = _esc(t.get("current_level") or "")
    recommendation = _esc(t.get("recommendation") or "")
    signals     = t.get("buying_signals") or []
    objections  = t.get("objections_raised") or []
    summary     = _esc(t.get("summary_ar") or t.get("summary") or "")
    next_action = _esc(t.get("next_action_ar") or t.get("next_action") or "")

    is_mail_valid = validate_email(email)
    mail_badge = '<span class="v-valid">✅ بريد صحيح</span>' if is_mail_valid else '<span class="v-invalid">⚠️ صيغة غير دقيقة</span>'
    if not email or email == "—": mail_badge = ""

    is_phone_valid, phone_msg = validate_international_phone(phone)
    phone_badge = f'<span class="{ "v-valid" if is_phone_valid else "v-invalid" }">{phone_msg}</span>'

    location = f"{city} ، {country}" if (city and country) else (city or country or "غير محدد")
    lang_map = {"ar": "العربية", "en": "الإنجليزية"}
    dialect_map = {"saudi": "لهجة سعودية 🇸🇦", "egyptian": "لهجة مصرية 🇪🇬", "syrian": "لهجة شامية 🇸🇾", "msa": "فصحى حديثة"}
    
    friendly_lang = lang_map.get(language.lower(), language)
    friendly_dialect = dialect_map.get(dialect.lower(), dialect)
    lang_full = f"{friendly_lang} ({friendly_dialect})" if dialect else friendly_lang

    wa = _wa_link(phone)
    wa_btn = (f'<a class="ticket-wa" href="{wa}" target="_blank">💬 تواصل عبر الواتساب</a>' if wa else "")
    
    products_chips = "".join(_chip(p, "#E0F2FE", "#0369A1") for p in products) or "<span style='color:#9CA3AF;'>—</span>"
    signals_chips = "".join(_chip(s, "#D1FAE5", "#065F46") for s in signals) or "<span style='color:#9CA3AF;'>—</span>"
    objections_chips = "".join(_chip(o, "#FEE2E2", "#991B1B") for o in objections) or "<span style='color:#9CA3AF;'>—</span>"

    card = (
        f'<div class="ticket-inner-body" dir="rtl">'
        f'<div class="card-section">'
        f'<div class="section-label">👤 هويّة العميل وبيانات التواصل (WHO)</div>'
        f'<div class="field-grid">'
        f'<div><span class="field-key">اسم العميل</span><span class="field-val">{name}</span></div>'
        f'<div><span class="field-key">رقم الهاتف الدولي</span><span class="field-val" dir="ltr"><bdi>{phone or "—"}</bdi></span> {phone_badge}</div>'
        f'<div><span class="field-key">الدولة / المدينة</span><span class="field-val">{location}</span></div>'
        f'<div><span class="field-key">قناة التواصل المفضلة</span><span class="field-val">{channel}</span></div>'
        f'<div><span class="field-key">لغة الحوار واللهجة</span><span class="field-val">{lang_full}</span></div>'
        f'<div><span class="field-key">البريد الإلكتروني</span><span class="field-val" dir="ltr">{email or "—"}</span> {mail_badge}</div>'
        f'</div></div>'

        f'<div class="card-section">'
        f'<div class="section-label">🎯 الكورسات والاهتمامات التعليمية (WHAT)</div>'
        f'<div class="field-grid">'
        f'<div style="grid-column: 1 / -1;"><span class="field-key">البرامج والدبلومات المهتم بها</span><span class="field-val">{products_chips}</span></div>'
        f'<div><span class="field-key">الهدف الوظيفي / الكارير</span><span class="field-val">{goal or "—"}</span></div>'
        f'<div><span class="field-key">المستوى التقني الحالي</span><span class="field-val">{level or "—"}</span></div>'
        f'<div style="grid-column: 1 / -1;" class="recommendation-container"><span class="field-key" style="color: #0369A1; font-weight: 700;">💡 توصية الذكاء الاصطناعي للمندوب على المكالمة</span><span class="field-val" style="color:#0369A1;">{recommendation or "—"}</span></div>'
        f'</div></div>'

        f'<div class="card-section">'
        f'<div class="section-label">📊 مؤشرات إغلاق البيع والجدية (HOW LIKELY)</div>'
        f'<div class="field-grid">'
        f'<div><span class="field-key">إشارات وبوادر الشراء</span><span class="field-val">{signals_chips}</span></div>'
        f'<div><span class="field-key">الاعتراضات والمخاوف المذكورة</span><span class="field-val">{objections_chips}</span></div>'
        f'</div></div>'

        f'<div class="card-section">'
        f'<div class="section-label">📝 ملخص المحادثة والإجراء القادم (WHAT HAPPENED)</div>'
        f'<div class="ticket-summary-title">خلاصة حوار العميل:</div>'
        f'<div class="ticket-summary-box">{summary or "—"}</div>'
        f'<div class="ticket-next-box"><b>◀ الخطوة القادمة للمبيعات:</b> {next_action or "—"}</div>'
        f'</div>'

        f'<div class="card-footer">{wa_btn}<span class="timestamp" dir="ltr"><bdi>{_fmt_time(t.get("created_at"))}</bdi></span></div>'
        f'</div>'
    )
    return card

def render_escalation_inner_body(t: dict) -> str:
    contact     = t.get("contact") or {}
    ticket_id   = _esc(t.get("ticket_id", ""))
    name        = _esc(contact.get("name") or "—")
    phone       = _esc(contact.get("phone") or "")
    city        = _esc(contact.get("city") or "")
    country     = _esc(contact.get("country") or "")
    language    = _esc(t.get("language") or "ar")
    dialect     = _esc(t.get("dialect") or "msa")
    reason      = _esc(t.get("reason") or "")
    recommendation = _esc(t.get("recommendation") or "")
    summary     = _esc(t.get("summary_ar") or t.get("summary") or "")
    next_action = _esc(t.get("next_action_ar") or t.get("next_action") or "")

    is_phone_valid, phone_msg = validate_international_phone(phone)
    phone_badge = f'<span class="{ "v-valid" if is_phone_valid else "v-invalid" }">{phone_msg}</span>'

    location = f"{city} ، {country}" if (city and country) else (city or country or "غير محدد")
    wa = _wa_link(phone)
    wa_btn = (f'<a class="ticket-wa escalation-wa" href="{wa}" target="_blank">⚠️ اتصال فوري للدعم</a>' if wa else "")

    card = (
        f'<div class="ticket-inner-body" dir="rtl">'
        f'<div class="card-section">'
        f'<div class="section-label">👤 بيانات العميل الأساسية (WHO)</div>'
        f'<div class="field-grid">'
        f'<div><span class="field-key">اسم العميل</span><span class="field-val">{name}</span></div>'
        f'<div><span class="field-key">رقم الهاتف الدولي</span><span class="field-val" dir="ltr"><bdi>{phone or "—"}</bdi></span> {phone_badge}</div>'
        f'<div><span class="field-key">الموقع الجغرافي</span><span class="field-val">{location}</span></div>'
        f'<div><span class="field-key">اللغة واللهجة</span><span class="field-val" dir="ltr">{language} — {dialect}</span></div>'
        f'</div></div>'

        f'<div class="card-section">'
        f'<div class="section-label">⚠️ سبب تصعيد التذكرة للمشرف البشري (REASON)</div>'
        f'<div class="reason-box">🚨 {reason or "—"}</div>'
        f'<div style="margin-top: 12px;" class="recommendation-container escal-rec"><span class="field-key" style="color:#B91C1C; font-weight:700;">💡 خطة التدخل الإداري الموصى بها</span><span class="field-val" style="color:#B91C1C;">{recommendation or "—"}</span></div>'
        f'</div>'

        f'<div class="card-section">'
        f'<div class="section-label">📝 موجز ما حدث في المحادثة (WHAT HAPPENED)</div>'
        f'<div class="ticket-summary-box">{summary or "—"}</div>'
        f'<div class="ticket-next-box" style="border-right-color: #B91C1C;"><b>▶ الإجراء المطلوب الحين:</b> {next_action or "—"}</div>'
        f'</div>'

        f'<div class="card-footer">{wa_btn}<span class="timestamp" dir="ltr"><bdi>{_fmt_time(t.get("created_at"))}</bdi></span></div>'
        f'</div>'
    )
    return card

# ─────────────────────────────────────────────────────────────────────
# CSS Injection
# ─────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    .crm-stat-box { background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 10px; padding: 12px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.02); margin-bottom: 20px; }
    .crm-stat-title { font-size: 11px; color: #6B7280; font-weight: 700; margin-bottom: 4px; }
    .crm-stat-num { font-size: 22px; font-weight: 800; color: #111827; }
    .total-box { border-top: 4px solid #4B5563; }
    .hot-box { border-top: 4px solid #EF4444; background: #FFFBFB; }
    .warm-box { border-top: 4px solid #3B82F6; background: #FAFAFF; }
    .cold-box { border-top: 4px solid #9CA3AF; }
    .escal-box { border-top: 4px solid #DC2626; background: #FFF5F5; }

    .stExpander { direction: rtl !important; text-align: right !important; border-radius: 12px !important; margin-bottom: 12px !important; background: #FFFFFF !important; border: 1px solid #E5E7EB !important; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.04) !important; }
    .stExpander [data-testid="stExpanderToggleIcon"] { margin-left: 0 !important; margin-right: auto !important; }
    .stExpander summary { flex-direction: row-reverse !important; justify-content: space-between !important; direction: rtl !important; text-align: right !important; }
    .stExpander p { text-align: right !important; direction: rtl !important; }
    
    .card-section { padding: 14px 0; border-top: 1px solid #F3F4F6; text-align: right; }
    .card-section:first-of-type { border-top: none; padding-top: 4px; }
    .section-label { font-size: 12px; font-weight: 700; color: #4B5563; margin-bottom: 10px; border-right: 3px solid #6B7280; padding-right: 8px; }
    .field-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px 24px; font-size: 14px; }
    .field-key { color: #6B7280; font-size: 11px; display: block; margin-bottom: 3px; font-weight: 600; }
    .field-val { color: #111827; font-weight: 600; }
    
    .v-valid { font-size: 10px; background: #D1FAE5; color: #065F46; padding: 2px 6px; border-radius: 4px; margin-right: 6px; font-weight: 700; }
    .v-invalid { font-size: 10px; background: #FEE2E2; color: #991B1B; padding: 2px 6px; border-radius: 4px; margin-right: 6px; font-weight: 700; }
    .recommendation-container { background: #F0F9FF; border: 1px solid #BAE6FD; padding: 10px 14px; border-radius: 8px; margin-top: 6px; }
    .recommendation-container.escal-rec { background: #FEF2F2; border: 1px solid #FCA5A5; }
    
    .ticket-summary-title { font-size: 13px; font-weight: 700; color: #374151; margin-bottom: 6px; }
    .ticket-summary-box { background: #F9FAFB; border: 1px solid #E5E7EB; padding: 12px; border-radius: 8px; font-size: 13.5px; color: #374151; line-height: 1.6; }
    .ticket-next-box { margin-top: 8px; background: #FFFBEB; border-right: 4px solid #D97706; padding: 8px 12px; border-radius: 4px; font-size: 13.5px; color: #92400E; }
    .reason-box { background: #FEF2F2; border-right: 4px solid #DC2626; padding: 12px; border-radius: 6px; color: #7F1D1D; font-size: 14px; font-weight: 600; }
    
    .card-footer { display: flex; justify-content: space-between; align-items: center; margin-top: 14px; padding-top: 12px; border-top: 1px solid #F3F4F6; }
    .ticket-wa { display: inline-block; background: #25D366; color: #FFFFFF !important; padding: 6px 14px; border-radius: 6px; font-size: 13px; font-weight: 700; text-decoration: none; }
    .ticket-wa:hover { background: #1ebd59; }
    .ticket-wa.escalation-wa { background: #DC2626; }
    .timestamp { font-size: 12px; color: #9CA3AF; font-weight: 500; }

    /* 🚨 الحل الجذري لـ RTL الحقيقي وصناديق التنبيهات الفارغة وعناوين التبويبات */
    div[data-testid="stTabs"] {
        direction: rtl !important;
    }
    
    div[data-testid="stTabs"] [data-baseweb="tab-list"] {
        direction: rtl !important;
        justify-content: flex-start !important;
        gap: 8px !important;
    }

    div[data-testid="stTabs"] [data-baseweb="tab"] {
        direction: rtl !important;
        text-align: right !important;
    }

    /* تحويل اتجاه وصناديق التنبيه الافتراضية التابعة لـ Streamlit إلى اليمين بنظام RTL */
    div[data-testid="stNotification"] {
        direction: rtl !important;
        text-align: right !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────────────────────────────
# Tabs Layout & Expandable Container Generation
# ─────────────────────────────────────────────────────────────────────
tab_leads, tab_esc, tab_analytics = st.tabs([
    f"🔥 العملاء المستهدفين ({n_leads})",
    f"⚠️ التصعيدات ({n_esc})",
    "📊 التحليلات"
])

# Tab 1: Leads
with tab_leads:
    lead_query = {"type": "lead"}
    fval = st.session_state.ticket_filter
    if fval in ('hot', 'warm', 'cold'):
        lead_query["$or"] = [
            {"temperature": {"$regex": f"^{fval}$", "$options": "i"}},
            {"lead_data.temperature": {"$regex": f"^{fval}$", "$options": "i"}}
        ]
    leads = list(db.tickets.find(lead_query, {"_id": 0}).sort("created_at", -1))

    # Apply search filter
    srch = st.session_state.ticket_search.strip().lower()
    if srch:
        leads = [t for t in leads if
                 srch in str(t.get("contact", {}).get("name") or "").lower() or
                 srch in str(t.get("contact", {}).get("phone") or "").lower() or
                 srch in str(t.get("contact", {}).get("email") or "").lower()]

    # Render Leads List
    if not leads:
        st.info("لا توجد تذاكر عملاء مهتمين حالياً مطابقة للبحث أو التصفية.")
    else:
        st.markdown('<div dir="rtl">', unsafe_allow_html=True)
        for t in leads:
            contact = t.get("contact") or {}
            name = _esc(contact.get("name") or "زائر غير مسجل")
            t_id = _esc(t.get("ticket_id", ""))
            
            # Extract lead temperature with root/legacy fallback
            temp_val = t.get("temperature")
            if not temp_val and "lead_data" in t and isinstance(t["lead_data"], dict):
                temp_val = t["lead_data"].get("temperature")
            temp = str(temp_val or "warm").lower()
            
            # Temperature styling
            emoji = "🔥" if temp == "hot" else ("🔹" if temp == "warm" else "❄️")
            temp_label = "ساخن" if temp == "hot" else ("مهتم" if temp == "warm" else "بارد")
            
            with st.expander(f"{emoji} عميل {temp_label}: {name} | (ID: {t_id})", expanded=(temp == "hot")):
                st.markdown(render_lead_inner_body(t), unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

# Tab 2: Escalations
with tab_esc:
    escalations = list(
        db.tickets.find({"type": "escalation"}, {"_id": 0})
        .sort("created_at", -1)
    )
    if not escalations:
        st.info("لا توجد تذاكر تصعيد (Escalation) حالياً.")
    else:
        st.markdown('<div dir="rtl">', unsafe_allow_html=True)
        for t in escalations:
            contact = t.get("contact") or {}
            name = _esc(contact.get("contact", {}).get("name") or "—")
            t_id = _esc(t.get("ticket_id", ""))
            
            with st.expander(f"🚨 تصعيد: {name} | (ID: {t_id})", expanded=False):
                st.markdown(render_escalation_inner_body(t), unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

# Tab 3: Analytics
with tab_analytics:
    st.markdown("""
    <div style="direction:rtl;text-align:right;margin-bottom:20px;">
        <h2 style="color:#1A1F4D;font-weight:800;">📊 لوحة التحليلات التفاعلية</h2>
        <p style="color:#6B7280;font-size:13px;">بيانات حية من المحادثات والتذاكر والعملاء</p>
    </div>
    """, unsafe_allow_html=True)

    # ── Fetch all data ──────────────────────────────────────────
    all_tickets  = list(db.tickets.find({}, {"_id": 0}))
    
    # Fetch sessions with extra fields for courses analysis
    all_sessions = list(db.sessions.find({}, {
        "_id": 0, "created_at": 1, "language": 1, "dialect": 1, 
        "products_of_interest": 1, "interested_courses": 1
    }))
    
    # Optional: fetch conversations if stored in a separate collection
    all_conversations = []
    if "conversations" in db.list_collection_names():
        all_conversations = list(db.conversations.find({}, {
            "_id": 0, "products_of_interest": 1, "interested_courses": 1
        }))

    leads_only = [t for t in all_tickets if t.get("type") == "lead"]
    escs_only  = [t for t in all_tickets if t.get("type") == "escalation"]

    # ── Row 1: KPI metrics ──────────────────────────────────────
    k1, k2, k3 = st.columns(3)
    k1.metric("إجمالي التذاكر",    n_total)
    k2.metric("معدل التحويل 🔥",  f"{round(hot/n_leads*100)}%" if n_leads else "0%")
    k3.metric("إجمالي الجلسات",   len(all_sessions))

    st.markdown("---")

    # ── Row 2: Lead temp pie + Lead vs Esc bar ──────────────────
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 🌡️ توزيع درجة حرارة العملاء")
        temp_counts = {"ساخن 🔥": hot, "مهتم 🔹": warm_display, "بارد ❄️": cold}
        fig_pie = px.pie(
            names=list(temp_counts.keys()),
            values=list(temp_counts.values()),
            color_discrete_sequence=["#EF4444", "#3B82F6", "#9CA3AF"],
            hole=0.4,
        )
        fig_pie.update_layout(
            margin=dict(t=10, b=10, l=10, r=10),
            legend=dict(orientation="h", yanchor="bottom", y=-0.2),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Cairo, sans-serif"),
        )
        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_pie, use_container_width=True)

    with col2:
        st.markdown("#### 📋 تذاكر Leads مقابل التصعيدات")
        fig_bar = px.bar(
            x=["عملاء Leads", "تصعيدات"],
            y=[n_leads, n_esc],
            color=["عملاء Leads", "تصعيدات"],
            color_discrete_map={"عملاء Leads": "#3B47C8", "تصعيدات": "#DC2626"},
            text_auto=True,
        )
        fig_bar.update_layout(
            margin=dict(t=10, b=10, l=10, r=10),
            showlegend=False,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Cairo, sans-serif"),
            yaxis=dict(showgrid=True, gridcolor="#F3F4F6"),
            xaxis=dict(showgrid=False),
        )
        fig_bar.update_traces(marker_line_width=0, textfont_size=14)
        st.plotly_chart(fig_bar, use_container_width=True)

    st.markdown("---")

    # ── Row 3: Most searched courses/diplomas ───────────────────
    st.markdown("#### 🎓 أكثر الكورسات والدبلومات طلباً")
    
    # Collect requested courses from both Tickets AND Sessions/Conversations
    all_products = []
    
    # 1. From Tickets (Leads)
    for t in leads_only:
        prods = t.get("products_of_interest") or []
        all_products.extend([p for p in prods if p])
        
    # 2. From all Sessions
    for s in all_sessions:
        prods = s.get("products_of_interest") or s.get("interested_courses") or []
        all_products.extend([p for p in prods if p])
        
    # 3. From all Conversations (if separate)
    for c in all_conversations:
        prods = c.get("products_of_interest") or c.get("interested_courses") or []
        all_products.extend([p for p in prods if p])

    if all_products:
        prod_counts = Counter(all_products).most_common(10)
        prod_names  = [p[0] for p in prod_counts]
        prod_vals   = [p[1] for p in prod_counts]

        fig_prod = px.bar(
            x=prod_vals, y=prod_names,
            orientation='h',
            color=prod_vals,
            color_continuous_scale=["#E8ECFF", "#3B47C8"],
            text=prod_vals,
        )
        fig_prod.update_layout(
            margin=dict(t=10, b=10, l=10, r=10),
            coloraxis_showscale=False,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Cairo, sans-serif"),
            yaxis=dict(autorange="reversed", showgrid=False),
            xaxis=dict(showgrid=True, gridcolor="#F3F4F6"),
            height=max(300, len(prod_names) * 42),
        )
        fig_prod.update_traces(textposition='outside', marker_line_width=0)
        st.plotly_chart(fig_prod, use_container_width=True)
    else:
        st.info("لا توجد بيانات منتجات بعد.")

    st.markdown("---")

    # ── Row 4: Language pie + Dialect bar ───────────────────────
    col3, col4 = st.columns(2)

    with col3:
        st.markdown("#### 🌍 توزيع لغات العملاء")
        lang_counts = Counter(t.get("language", "ar") for t in leads_only)
        lang_map    = {"ar": "العربية", "en": "الإنجليزية"}
        fig_lang = px.pie(
            names=[lang_map.get(k, k) for k in lang_counts.keys()],
            values=list(lang_counts.values()),
            color_discrete_sequence=["#3B47C8", "#E77C24", "#10B981"],
            hole=0.4,
        )
        fig_lang.update_layout(
            margin=dict(t=10, b=10, l=10, r=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Cairo, sans-serif"),
            legend=dict(orientation="h", yanchor="bottom", y=-0.2),
        )
        fig_lang.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_lang, use_container_width=True)

    with col4:
        st.markdown("#### 🗣️ توزيع اللهجات")
        dialect_map = {
            "egyptian": "مصرية 🇪🇬", "saudi": "سعودية 🇸🇦",
            "syrian": "شامية 🇸🇾",   "msa": "فصحى",
            "en": "إنجليزية"
        }
        dialect_counts = Counter(t.get("dialect", "msa") for t in leads_only)
        d_names = [dialect_map.get(k, k) for k in dialect_counts.keys()]
        d_vals  = list(dialect_counts.values())

        fig_dialect = px.bar(
            x=d_names, y=d_vals,
            color=d_names,
            color_discrete_sequence=["#3B47C8","#E77C24","#10B981","#6366F1","#F59E0B"],
            text_auto=True,
        )
        fig_dialect.update_layout(
            margin=dict(t=10, b=10, l=10, r=10),
            showlegend=False,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Cairo, sans-serif"),
            yaxis=dict(showgrid=True, gridcolor="#F3F4F6"),
            xaxis=dict(showgrid=False),
        )
        fig_dialect.update_traces(marker_line_width=0)
        st.plotly_chart(fig_dialect, use_container_width=True)

    st.markdown("---")

    # ── Row 5: Sessions over time ───────────────────────────────
    st.markdown("#### 💬 الجلسات والمحادثات بمرور الوقت")
    if all_sessions:
        sess_df = pd.DataFrame(all_sessions)
        if "created_at" in sess_df.columns:
            sess_df["created_at"] = pd.to_datetime(sess_df["created_at"], errors="coerce")
            sess_df = sess_df.dropna(subset=["created_at"])
            sess_df["date"] = sess_df["created_at"].dt.date
            daily = sess_df.groupby("date").size().reset_index(name="جلسات")

            fig_sess = px.bar(
                daily, x="date", y="جلسات",
                color_discrete_sequence=["#3B47C8"],
                text_auto=True,
            )
            fig_sess.update_layout(
                margin=dict(t=10, b=10, l=10, r=10),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(family="Cairo, sans-serif"),
                xaxis_title="التاريخ", yaxis_title="عدد الجلسات",
                yaxis=dict(showgrid=True, gridcolor="#F3F4F6"),
                xaxis=dict(showgrid=False),
            )
            fig_sess.update_traces(marker_line_width=0)
            st.plotly_chart(fig_sess, use_container_width=True)
    else:
        st.info("لا توجد بيانات جلسات بعد.")

    # ── Row 6: Buying signals word frequency ────────────────────
    st.markdown("---")
    st.markdown("#### 📈 أبرز إشارات الشراء")
    all_signals = []
    for t in leads_only:
        all_signals.extend(t.get("buying_signals") or [])

    if all_signals:
        sig_counts = Counter(all_signals).most_common(8)
        fig_sig = px.bar(
            x=[s[1] for s in sig_counts],
            y=[s[0] for s in sig_counts],
            orientation='h',
            color=[s[1] for s in sig_counts],
            color_continuous_scale=["#D1FAE5", "#065F46"],
            text=[s[1] for s in sig_counts],
        )
        fig_sig.update_layout(
            margin=dict(t=10, b=10, l=10, r=10),
            coloraxis_showscale=False,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Cairo, sans-serif"),
            yaxis=dict(autorange="reversed", showgrid=False),
            xaxis=dict(showgrid=True, gridcolor="#F3F4F6"),
        )
        fig_sig.update_traces(textposition='outside', marker_line_width=0)
        st.plotly_chart(fig_sig, use_container_width=True)
    else:
        st.info("لا توجد إشارات شراء مسجّلة بعد.")
