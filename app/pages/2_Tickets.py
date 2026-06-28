import sys
import os
import re
from pathlib import Path
from datetime import datetime, timezone
import html as _html

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

st.title("🎫 CRM Tickets Dashboard")
st.markdown("---")

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
    'تذاكر العملاء المستخرجة بواسطة الـ الذكاء الاصطناعي والتصعيدات البشرية الفورية. تظهر التذاكر الساخنة أولاً.</p>',
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────────────────────────────
# CRM Stats Columns
# ─────────────────────────────────────────────────────────────────────
st.markdown("<div dir='rtl' style='margin-bottom: 10px;'>", unsafe_allow_html=True)
stat_col1, stat_col2, stat_col3, stat_col4, stat_col5 = st.columns(5)

with stat_col1:
    st.markdown(
        f'<div class="crm-stat-box total-box">'
        f'<div class="crm-stat-title">إجمالي التذاكر</div>'
        f'<div class="crm-stat-num">{n_total}</div>'
        f'</div>', unsafe_allow_html=True
    )
with stat_col2:
    st.markdown(
        f'<div class="crm-stat-box hot-box">'
        f'<div class="crm-stat-title">عملاء ساخنين 🔥</div>'
        f'<div class="crm-stat-num">{hot}</div>'
        f'</div>', unsafe_allow_html=True
    )
with stat_col3:
    st.markdown(
        f'<div class="crm-stat-box warm-box">'
        f'<div class="crm-stat-title">عملاء مهتمين 🔹</div>'
        f'<div class="crm-stat-num">{warm_display}</div>'
        f'</div>', unsafe_allow_html=True
    )
with stat_col4:
    st.markdown(
        f'<div class="crm-stat-box cold-box">'
        f'<div class="crm-stat-title">عملاء باردين ❄️</div>'
        f'<div class="crm-stat-num">{cold}</div>'
        f'</div>', unsafe_allow_html=True
    )
with stat_col5:
    st.markdown(
        f'<div class="crm-stat-box escal-box">'
        f'<div class="crm-stat-title">تصعيد بشري ⚠️</div>'
        f'<div class="crm-stat-num">{n_esc}</div>'
        f'</div>', unsafe_allow_html=True
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
    
    # --- FALLBACK LOGIC ---
    # Look at root 'temperature' first (new), then fallback to nested (old)
    temp_val = t.get("temperature")
    if not temp_val and "lead_data" in t and isinstance(t["lead_data"], dict):
        temp_val = t["lead_data"].get("temperature")
    
    temp = str(temp_val or "warm").lower()
    # ----------------------

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
tab_leads, tab_esc = st.tabs([f"🔥 العملاء المستهدفين Leads ({n_leads})", f"⚠️ طلبات التصعيد البشري ({n_esc})"])

with tab_leads:
    leads = list(
        db.tickets.find({"type": "lead"}, {"_id": 0})
        .sort([("created_at", -1)])
    )
    if not leads:
        st.info("لا توجد تذاكر عملاء (Leads) بعد.")
    else:
        st.markdown('<div dir="rtl">', unsafe_allow_html=True)
        for t in leads:
            contact = t.get("contact") or {}
            name = _esc(contact.get("name") or "زائر غير مسجل")
            
            # --- SAME FALLBACK LOGIC ---
            temp_val = t.get("temperature")
            if not temp_val and "lead_data" in t and isinstance(t["lead_data"], dict):
                temp_val = t["lead_data"].get("temperature")
            temp = str(temp_val or "warm").lower()
            # ---------------------------
            
            t_id = _esc(t.get("ticket_id", ""))
            
            temp_icon = "🔥 ساخن جداً" if temp == "hot" else "🔹 مهتم" if temp == "warm" else "❄️ بارد"
            
            with st.expander(f"👤 {name} | {temp_icon} (ID: {t_id})", expanded=False):
                st.markdown(render_lead_inner_body(t), unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

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
            name = _esc(contact.get("name") or "—")
            t_id = _esc(t.get("ticket_id", ""))
            
            with st.expander(f"🚨 تصعيد: {name} | (ID: {t_id})", expanded=False):
                st.markdown(render_escalation_inner_body(t), unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)