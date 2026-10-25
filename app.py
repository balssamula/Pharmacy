import streamlit as st
import os
import hmac
import hashlib
import requests
import json
import base64
import time
from datetime import datetime, timedelta
from utils import get_headers, safe_api_request, get_branches_list
from token_store import is_configured, list_stores, get_store, save_credentials, store_health
import logging
logging.getLogger('streamlit').setLevel(logging.ERROR)

st.set_page_config(
    page_title="مدير المنظومة المركزي",
    layout="wide",
    page_icon="👑",
    initial_sidebar_state="expanded"
)

from offers_page import render_offers_page
from products_page import render_products_page
from customers_page import render_customers_page
from orders_page import render_orders_page

# ==========================================
# 🔄 المزامنة الحية فائقة السرعة (مع شريط التقدم الذكي)
# ==========================================
@st.cache_resource
def get_global_store_cache():
    """مخزن ذاكرة السيرفر المركزي (يعيش حتى عند تحديث الصفحة أو إغلاق المتصفح)"""
    return {}

def fetch_store_data_fast(token, headers):
    cache = get_global_store_cache()
    now = datetime.now()
    
    if token in cache and (now - cache[token]['time']).total_seconds() < 900:
        return cache[token]['products'], cache[token]['offers'], cache[token]['po_map'], cache[token]['customers']
        
    status_text = st.empty()
    progress_bar = st.progress(0)
    
    # 1️⃣ سحب المنتجات
    status_text.info("📦 جاري تهيئة الاتصال وسحب المنتجات...")
    products = []
    res = safe_api_request("GET", "https://api.salla.dev/admin/v2/products?per_page=60&page=1", headers)
    if res:
        tp = res.get("pagination", {}).get("totalPages", 1)
        products.extend(res.get("data", []))
        for page in range(2, tp + 1):
            status_text.info(f"📦 جاري سحب المنتجات: صفحة {page} من {tp} | (تم تحميل {len(products)} منتج)")
            p_res = safe_api_request("GET", f"https://api.salla.dev/admin/v2/products?per_page=60&page={page}", headers)
            if p_res and p_res.get("data"): products.extend(p_res["data"])
            progress_bar.progress(0.3 * (page / tp))
            
    # 2️⃣ سحب العروض
    status_text.info("🎁 جاري سحب العروض الخاصة النشطة...")
    offers = []
    o_res = safe_api_request("GET", "https://api.salla.dev/admin/v2/specialoffers?per_page=60&page=1", headers)
    if o_res:
        tp = o_res.get("pagination", {}).get("totalPages", 1)
        offers.extend(o_res.get("data", []))
        for page in range(2, tp + 1):
            status_text.info(f"🎁 جاري سحب العروض: صفحة {page} من {tp} | (تم تحميل {len(offers)} عرض)")
            op_res = safe_api_request("GET", f"https://api.salla.dev/admin/v2/specialoffers?per_page=60&page={page}", headers)
            if op_res and op_res.get("data"): offers.extend(op_res["data"])
            progress_bar.progress(0.3 + (0.3 * (page / tp)))

    # 3️⃣ سحب العملاء بالكامل (لحل مشكلة عدم ظهورهم)
    status_text.info("👥 جاري سحب قاعدة بيانات العملاء...")
    customers = []
    c_res = safe_api_request("GET", "https://api.salla.dev/admin/v2/customers?per_page=100&page=1", headers)
    if c_res:
        tp = c_res.get("pagination", {}).get("totalPages", 1)
        # Respect documented pagination for complete catalogues; do not impose an invisible truncation.
        customers.extend(c_res.get("data", []))
        for page in range(2, tp + 1):
            status_text.info(f"👥 جاري سحب العملاء: صفحة {page} من {tp} | (تم تحميل {len(customers)} عميل)")
            cp_res = safe_api_request("GET", f"https://api.salla.dev/admin/v2/customers?per_page=100&page={page}", headers)
            if cp_res and cp_res.get("data"): customers.extend(cp_res["data"])
            progress_bar.progress(0.6 + (0.3 * (page / tp)))
            
    # 4️⃣ معالجة الروابط
    status_text.info("🔗 جاري معالجة روابط العروض بالمنتجات...")
    po_map = {"ALL_PRODUCTS": []}
    active_offers = [o for o in offers if o.get('status') == 'active']
    for o in active_offers:
        oid = str(o.get("id"))
        summary = {"id": oid, "name": o.get("name")}
        applied_to = o.get("applied_to")
        offer_type = o.get("offer_type")
        if applied_to in ["order", "all"] or offer_type in ["cart_offer", "tiered_offer"]:
            po_map["ALL_PRODUCTS"].append(summary)
        else:
            pids = set()
            for px in (o.get("buy", {}) or {}).get("products", []):
                pid = str(px.get("id", px) if isinstance(px, dict) else px)
                if pid.isdigit(): pids.add(pid)
            for px in (o.get("get", {}) or {}).get("products", []):
                pid = str(px.get("id", px) if isinstance(px, dict) else px)
                if pid.isdigit(): pids.add(pid)
            for px in o.get("products", []):
                pid = str(px.get("id", px) if isinstance(px, dict) else px)
                if pid.isdigit(): pids.add(pid)
            for pid in pids:
                if pid not in po_map: po_map[pid] = []
                po_map[pid].append(summary)
    
    progress_bar.progress(1.0)
    status_text.success(f"✅ اكتمل التحميل! ({len(products)} منتج، {len(offers)} عرض، {len(customers)} عميل)")
    progress_bar.empty()
    status_text.empty()
    
    cache[token] = {
        'time': now,
        'products': products,
        'offers': offers,
        'po_map': po_map,
        'customers': customers
    }
    
    return products, offers, po_map, customers

def fetch_all_customers_with_progress(headers):
    all_customers = []
    page = 1
    per_page = 200
    total_pages = 1
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # أولاً جلب الصفحة الأولى لمعرفة العدد الإجمالي
    first_res = safe_api_request("GET", f"https://api.salla.dev/admin/v2/customers?per_page={per_page}&page=1", headers)
    if first_res:
        total_pages = first_res.get('pagination', {}).get('totalPages', 1)
        all_customers.extend(first_res.get('data', []))
    
    for page in range(2, total_pages + 1):
        status_text.text(f"جلب العملاء: صفحة {page} من {total_pages}")
        progress_bar.progress(page / total_pages)
        
        url = f"https://api.salla.dev/admin/v2/customers?per_page={per_page}&page={page}"
        res = safe_api_request("GET", url, headers)
        if res and res.get('data'):
            all_customers.extend(res['data'])
    
    progress_bar.empty()
    status_text.empty()
    return all_customers
    
def perform_initial_sync_with_ui(headers):
    placeholder = st.empty()
    with placeholder.container():
        st.markdown("<div style='background: #0F1C2E; padding: 20px; border-radius: 12px; border: 1px solid #00EBCF; text-align: center; margin-bottom: 20px;'><h3 style='color: #00EBCF; margin: 0;'>🚀 جاري تهيئة المنظومة وسحب بيانات المتجر الشاملة...</h3></div>", unsafe_allow_html=True)
        
        token = headers['Authorization'].split(' ')[1]
        products, offers, po_map, customers = fetch_store_data_fast(token, headers)
        
        st.session_state["all_products"] = products
        st.session_state["all_offers"] = offers
        st.session_state["product_offers_map"] = po_map
        st.session_state["customers_data"] = {"data": customers}
        
        from utils import get_branches_list
        st.session_state["branches"] = get_branches_list()
        st.session_state["all_products_fetched"] = True
        st.session_state["last_sync_time"] = datetime.now().strftime("%Y-%m-%d %I:%M %p")
    placeholder.empty()

# ==========================================
# 🎨 CSS
# ==========================================
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
    html, body, .stApp, h1, h2, h3, h4, h5, h6, p, label, input, select, textarea, div[data-testid="stMarkdownContainer"] p, div.stSelectbox div { font-family: 'Cairo', sans-serif !important; }
    .stIcon, [data-testid="stIcon"], [class^="st-"] svg, svg, i, span[data-testid="stIconVisibility"], summary svg, button svg, [data-base-ui="icon"], [class*="Icon"], summary::after, .st-emotion-cache-p6w706, .st-emotion-cache-1n76uvr, [data-testid="stExpander"] svg { font-family: inherit !important; }
    div.stButton > button[data-testid="baseButton-primary"] { background-color: #00EBCF !important; color: #0f1c2e !important; font-weight: bold !important; border-radius: 8px !important; }
    div.stButton > button[data-testid="baseButton-primary"]:hover { transform: scale(1.02) !important; box-shadow: 0 4px 15px rgba(0,235,207,0.4) !important; }
    div[data-testid="stPopover"] button { background-color: #0f5132 !important; color: #ffffff !important; border-radius: 8px !important; }
    div.stButton > button[key*="t_dl_"] { background-color: #dc3545 !important; color: #ffffff !important; border: 1px solid #dc3545 !important; }
    [data-testid="stSidebar"] { background-color: #0f1c2e !important; padding: 20px 15px !important; }
    [data-testid="stSidebar"] * { color: #ffffff !important; }
    .stButton button { border-radius: 8px !important; font-weight: 600 !important; }
    [data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child { display: none !important; }
    [data-testid="stSidebar"] div[role="radiogroup"] label > div:nth-child(2) { width: 100% !important; margin: 0 !important; }
    [data-testid="stSidebar"] div[role="radiogroup"] label { background: linear-gradient(135deg, #1E293B 0%, #0F1C2E 100%); padding: 14px 15px !important; margin-bottom: 16px !important; border-radius: 8px !important; transform: skewX(-12deg); border: 1px solid #334155; cursor: pointer; display: flex; align-items: center; }
    [data-testid="stSidebar"] div[role="radiogroup"] label div[data-testid="stMarkdownContainer"] { transform: skewX(12deg); text-align: center; width: 100%; }
    [data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) { background: linear-gradient(135deg, #00EBCF 0%, #0284C7 100%) !important; border-color: #00EBCF !important; }
    .blinking-dot { height: 12px; width: 12px; background-color: #10B981; border-radius: 50%; display: inline-block; box-shadow: 0 0 8px #10B981; animation: blinker 1.5s linear infinite; }
    @keyframes blinker { 50% { opacity: 0.3; box-shadow: 0 0 2px #10B981; } }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 🔐 نظام الدخول المطور (لوحة تحكم المدير)
# ==========================================

if "is_admin_logged_in" not in st.session_state: st.session_state["is_admin_logged_in"] = False
if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
def _admin_setting(key):
    val = os.environ.get(key, "")
    if not val:
        try:
            val = str(st.secrets.get(key, ""))
        except (FileNotFoundError, KeyError, AttributeError):
            pass
    return val


def _verify_admin_credentials(username, password):
    stored_user = _admin_setting("ADMIN_USERNAME")
    password_hash = _admin_setting("ADMIN_PASSWORD_HASH")
    if not stored_user or not password_hash or not hmac.compare_digest(username, stored_user):
        return False
    # Format: pbkdf2_sha256$iterations$salt_hex$hash_hex
    try:
        algorithm, iterations, salt_hex, expected_hex = password_hash.split("$")
        if algorithm != "pbkdf2_sha256" or not 200000 <= int(iterations) <= 2000000:
            return False
        calculated = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations))
        return hmac.compare_digest(calculated, bytes.fromhex(expected_hex))
    except (ValueError, TypeError):
        return False

# --- الشاشة الأولى: تسجيل دخول المدير ---
if not st.session_state["is_admin_logged_in"]:
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    _, col_login, _ = st.columns([1, 1.5, 1])
    
    with col_login:
        with st.container(border=True):
            st.markdown("<h2 style='text-align:center; color:#00EBCF; margin-bottom: 20px;'>👑 الإدارة المركزية للتطبيقات</h2>", unsafe_allow_html=True)
            
            if not _admin_setting("ADMIN_USERNAME") or not _admin_setting("ADMIN_PASSWORD_HASH"):
                st.error("إعداد حساب المدير غير مكتمل. اضبط ADMIN_USERNAME و ADMIN_PASSWORD_HASH في Streamlit secrets.")
                st.stop()
            un = st.text_input("👤 اسم المستخدم الإداري:")
            pw = st.text_input("🔒 كلمة المرور:", type="password")
            
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🚀 تسجيل الدخول للوحة التحكم", use_container_width=True, type="primary"):
                if _verify_admin_credentials(un, pw):
                    st.session_state["is_admin_logged_in"] = True
                    st.rerun()
                else:
                    st.error("❌ بيانات الدخول غير صحيحة!")
    st.stop()

# --- الشاشة الثانية: لوحة اختيار المتاجر ---
if st.session_state["is_admin_logged_in"] and not st.session_state["logged_in"]:
    st.markdown("""
    <div style="background: linear-gradient(135deg, #1E293B 0%, #0F1C2E 100%); padding: 25px; border-radius: 12px; color: white; text-align: center; margin-bottom: 30px; border-bottom: 4px solid #00EBCF;">
        <h1 style="color: white; margin: 0;">🌐 لوحة التحكم المركزية للمتاجر المربوطة</h1>
        <p style="color: #94A3B8; margin-top: 5px;">اختر المتجر الذي ترغب في إدارته من القائمة أدناه</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Supabase is the only authoritative token store in this release.
    if not is_configured():
        st.error("⛔ أضف SUPABASE_URL و SUPABASE_SERVICE_ROLE_KEY إلى Streamlit Secrets أولاً.")
        st.stop()
    try:
        connected_stores = list_stores()
    except RuntimeError as exc:
        st.error(str(exc))
        st.stop()

    st.subheader("🛡️ حالة ربط المتاجر وتجديد رموز سلة")
    st.caption("المواعيد وحالة التجديد من Supabase، وليس من ملف GitHub. لا تظهر الرموز لأي مستخدم.")
    if st.button("🔄 تحديث حالة جميع المتاجر", key="refresh_store_status"):
        st.rerun()

    with st.expander("📦 نقل الرموز الموجودة في stores.json لمرة واحدة", expanded=not bool(connected_stores)):
        st.warning("الرموز القديمة قد تكون منتهية. سنستوردها بحالة «يحتاج مراجعة» ولن تعمل عليها مهمة التجديد حتى تُفحص وتُعتمد من خلال حفظ زوج صالح جديد.")
        confirm_legacy = st.checkbox("أؤكد أن لدي نسخة احتياطية وأن النقل سيُنفّذ دون استبدال رموز Supabase", key="confirm_legacy")
        if st.button("استيراد المتاجر غير الموجودة فقط", disabled=not confirm_legacy, key="import_old_tokens"):
            added, skipped = 0, 0
            try:
                with open("stores.json", "r", encoding="utf-8") as f:
                    legacy = json.load(f)
                for row in legacy if isinstance(legacy, list) else []:
                    mid = str(row.get("merchant_id") or "").strip()
                    if not (mid and row.get("access_token") and row.get("refresh_token")):
                        skipped += 1
                        continue
                    # Old JSON may not record issuance date. Schedule a refresh soon,
                    # using the latest pair exactly once; no automatic OAuth request here.
                    if save_credentials(mid, row.get("store_name") or mid,
                                        row["access_token"], row["refresh_token"],
                                        days_left=0.05, replace=False,
                                        initial_status="review_required"):
                        added += 1
                    else:
                        skipped += 1
                st.success(f"تم استيراد {added} متجر بحالة تحتاج مراجعة، وتخطي {skipped}. لا تُشغّل Cron قبل إدخال زوج حديث صالح والتحقق منه.")
                st.rerun()
            except (OSError, ValueError, RuntimeError, TypeError) as exc:
                st.error("تعذر الاستيراد. تحقق من وجود الملف وجدول Supabase؛ لن نعرض الرموز في سجل الأخطاء.")

    with st.expander("🔐 إدخال زوج رموز جديد لمتجر محدد (عند الضرورة)"):
        with st.form("manual_oauth_pair_form", clear_on_submit=True):
            merchant_input = st.text_input("معرف التاجر (merchant_id) - إلزامي")
            name_input = st.text_input("اسم المتجر")
            access_input = st.text_input("Access Token", type="password")
            refresh_input = st.text_input("Refresh Token", type="password")
            valid_days = st.number_input("الأيام المتبقية تقريبًا من صلاحية Access Token", min_value=1, max_value=14, value=14)
            replace_existing = st.checkbox("أوافق على استبدال رموز المتجر المحدد الموجودة في Supabase")
            if st.form_submit_button("💾 حفظ الزوج في Supabase", type="primary"):
                try:
                    result = save_credentials(merchant_input, name_input or merchant_input,
                                              access_input, refresh_input,
                                              days_left=float(valid_days), replace=replace_existing)
                    if result:
                        st.success("حُفظ الزوج في Supabase دون كتابة أي رموز في GitHub.")
                        st.rerun()
                    else:
                        st.warning("المتجر موجود بالفعل؛ لم يُستبدل. فعّل الموافقة الصريحة للاستبدال.")
                except (ValueError, RuntimeError) as exc:
                    st.error(str(exc))

    if connected_stores:
        cols = st.columns(3)
        for idx, store in enumerate(connected_stores):
            with cols[idx % 3]:
                with st.container(border=True):
                    from html import escape as escape_html
                    safe_name = escape_html(str(store.get("store_name") or "متجر"))
                    safe_merchant = escape_html(str(store.get("merchant_id") or ""))
                    label, status, days_left = store_health(store)
                    st.markdown(f"### 🏪 {safe_name}")
                    st.caption(f"معرف التاجر: {safe_merchant}")
                    st.write(label)
                    st.caption("الحالة حسب التجديد المخزّن؛ لا تمثل اختبار API مباشرًا")
                    if days_left is not None:
                        st.write(f"🕒 المتبقي: {days_left:.1f} يوم" if days_left >= 0 else "⛔ انتهت صلاحية رمز الوصول")
                    if store.get("token_updated_at"):
                        st.caption(f"آخر حفظ للرموز: {str(store['token_updated_at'])[:16]} UTC")
                    if store.get("last_successful_refresh_at"):
                        st.caption(f"آخر تجديد ناجح: {str(store['last_successful_refresh_at'])[:16]} UTC")
                    if store.get("last_refresh_attempt_at"):
                        st.caption(f"آخر محاولة تجديد: {str(store['last_refresh_attempt_at'])[:16]} UTC")
                    if store.get("last_error"):
                        st.warning(f"تحتاج مراجعة: {str(store['last_error'])[:160]}")
                    if st.button("🔑 إدارة هذا المتجر", key=f"login_store_{store.get('merchant_id')}",
                                 use_container_width=True, type="primary",
                                 disabled=(status in ('reconnect_required', 'refreshing') or
                                           (days_left is not None and days_left <= 0))):
                        token = store.get("access_token")
                        if not token or not str(store.get("merchant_id") or "").strip():
                            st.error("بيانات الربط غير مكتملة")
                            st.stop()
                        headers = {"Authorization": f"Bearer {token}"}
                        st.session_state["merchant_id"] = str(store.get("merchant_id"))
                        st.session_state["store_name"] = store.get("store_name")
                        st.session_state["logged_in"] = True
                        st.session_state["access_token"] = token
                        st.session_state["login_time"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                        perform_initial_sync_with_ui(headers)
                        st.rerun()
    else:
        st.info("لا توجد متاجر في المخزن الجديد. استخدم استيراد الملف القديم أو أدخل الرموز في النموذج الآمن.")

    # زر تسجيل الخروج للمدير
    st.divider()
    if st.button("🚪 تسجيل الخروج من حساب المدير", type="secondary"):
        st.session_state["is_admin_logged_in"] = False
        st.rerun()
        
    st.stop() # إيقاف الكود هنا حتى يختار المدير متجراً

# Re-read the latest token on each Streamlit rerun; the Edge Function may have rotated it.
if st.session_state.get("logged_in") and st.session_state.get("merchant_id"):
    try:
        current_store = get_store(st.session_state["merchant_id"])
        if current_store and current_store.get("access_token"):
            if current_store.get("connection_status") == "reconnect_required":
                st.error("ربط المتجر يحتاج إعادة تفويض من سلة؛ لا تستخدم الرموز القديمة.")
                st.session_state["logged_in"] = False
                st.stop()
            st.session_state["access_token"] = current_store["access_token"]
    except RuntimeError as exc:
        st.error(str(exc))
        st.stop()

# ==========================================
# 🏠 الواجهة الرئيسية (بعد اختيار المتجر)
# ==========================================
st.markdown("""
<div style="background: linear-gradient(135deg, #1E293B 0%, #3B82F6 100%); padding: 25px; border-radius: 12px; color: white; text-align: center; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
    <h1 style="color: white; margin: 0; font-size: 2.2rem;">🎁 منظومة إدارة المنتجات والعروض الخاصة</h1>
</div>
""", unsafe_allow_html=True)

# ✅ تثبيت معرف التطبيق
FIXED_APP_ID = "277610741"

# ✅ جلب بيانات الاشتراك تلقائياً للمتجر الحالي وحفظها في الذاكرة (بدون تدخل يدوي)
if "app_subscription_data" not in st.session_state:
    headers_sub = {"Authorization": f"Bearer {st.session_state.get('access_token')}"}
    # جلب الاشتراكات الخاصة بهذا المتجر (عبر التوكن الخاص به)
    res_sub = safe_api_request("GET", f"https://api.salla.dev/admin/v2/apps/{FIXED_APP_ID}/subscriptions", headers_sub)
    if res_sub and res_sub.get("data") and len(res_sub["data"]) > 0:
        st.session_state["app_subscription_data"] = res_sub["data"][0] # حفظ أول اشتراك فعال
    else:
        st.session_state["app_subscription_data"] = None

# استخراج رقم الاشتراك والباقة والرصيد لعرضها بذكاء
current_sub = st.session_state.get("app_subscription_data")
sub_id_display = current_sub.get("id") if current_sub else "غير متوفر"
plan_name_display = current_sub.get("plan_name") if current_sub else "لا توجد باقة"
balance_display = current_sub.get("subscription_balance", 0) if current_sub else 0

st.sidebar.markdown(f"""
<div style="background: linear-gradient(135deg, #0F1C2E, #1a365d); padding: 20px 15px; border-radius: 12px; border: 1px solid #334155; margin-bottom: 25px; box-shadow: 0 4px 10px rgba(0,0,0,0.2); position: relative; overflow: hidden;">
<div style="position: absolute; top: 0; right: 0; background: linear-gradient(90deg, #F59E0B, #D97706); color: #FFF; padding: 4px 12px; border-bottom-left-radius: 12px; font-weight: bold; font-size: 12px; box-shadow: -2px 2px 8px rgba(0,0,0,0.3); z-index: 10;">
🆔 App ID: {FIXED_APP_ID}
</div>
<div style="text-align: center; margin-bottom: 12px; margin-top: 15px;">
<div style="font-size: 32px; margin-bottom: 5px;">🏪</div>
<h3 style="color: #FFFFFF; margin: 0; font-size: 18px;">{st.session_state.get('store_name', 'متجرك')}</h3>
<div style="margin-top: 12px; background: rgba(0, 235, 207, 0.1); border: 1px solid rgba(0, 235, 207, 0.3); border-radius: 8px; padding: 8px; font-size: 13px;">
<div style="margin-bottom: 4px;"><span style="color: #94A3B8;">💳 رقم الاشتراك:</span> <b style="color: #00EBCF;">{sub_id_display}</b></div>
<div><span style="color: #94A3B8;">🏷️ الباقة:</span> <b style="color: #FBBF24;">{plan_name_display}</b></div>
</div>
</div>
<div style="background: rgba(0,0,0,0.2); border-radius: 8px; padding: 10px;">
<div style="display: flex; align-items: center; justify-content: center; font-size: 14px; margin-bottom: 8px; gap: 8px;">
<span class="blinking-dot"></span><span style="color: #10B981; font-weight: bold;">متصل ومزامن لحظياً</span>
</div>
<div style="text-align: center; font-size: 12px; color: #94A3B8; border-top: 1px dashed #334155; padding-top: 8px; margin-top: 5px;">
آخر دخول: <b style="color: #CBD5E1; direction: ltr; display: inline-block;">{st.session_state.get('last_sync_time', '')}</b>
</div>
</div>
</div>
""", unsafe_allow_html=True)

# ==========================================
# ✅ أزرار إدارة اشتراكات التطبيق والإعدادات
# ==========================================

with st.sidebar.popover("📋 تفاصيل واشتراكات التطبيق", use_container_width=True):
    st.markdown("<b style='color:#0f1c2e;'>🔍 استعلام وتحديث بيانات الاشتراك</b>", unsafe_allow_html=True)
    if st.button("تحديث وعرض التفاصيل", key="btn_sub_info", use_container_width=True, type="primary"):
        headers = {"Authorization": f"Bearer {st.session_state.get('access_token')}"}
        with st.spinner("⏳"):
            res = safe_api_request("GET", f"https://api.salla.dev/admin/v2/apps/{FIXED_APP_ID}/subscriptions", headers)
            if res and res.get("data"):
                st.success("✅ جلب البيانات بنجاح!")
                st.session_state["app_subscription_data"] = res["data"][0] # تحديث الذاكرة
                subs = res["data"]
                for sub in subs:
                    app_name = sub.get("app_name", "غير معروف")
                    plan_name = sub.get("plan_name", "غير معروف")
                    plan_type = sub.get("plan_type", "")
                    price = sub.get("price", "0")
                    s_date = sub.get("start_date") or "غير محدد"
                    e_date = sub.get("end_date") or "غير محدد"
                    balance = sub.get("subscription_balance")
                    balance_text = str(balance) if balance is not None else "لا يوجد (غير مطبق)"
                    
                    type_ar = {"once": "مرة واحدة", "recurring": "متكرر (دوري)", "on_demand": "حسب الاستهلاك", "free": "مجاني"}.get(plan_type, plan_type)
                    st.markdown(f"""
                    <div style="background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; padding: 15px; margin-top: 10px; text-align: right;">
                        <h4 style="color: #0f1c2e; margin-top: 0; margin-bottom: 10px;">📱 {app_name}</h4>
                        <p style="margin: 5px 0; font-size: 14px;"><b>الباقة:</b> {plan_name} <span style="color: #64748b; font-size: 12px;">({type_ar})</span></p>
                        <p style="margin: 5px 0; font-size: 14px;"><b>السعر:</b> <span style="color: #059669; font-weight: bold;">{price} ر.س</span></p>
                        <p style="margin: 5px 0; font-size: 14px;"><b>رصيد الاستهلاك:</b> <span style="color: #ea580c;">{balance_text}</span></p>
                        <hr style="margin: 10px 0; border-top: 1px dashed #cbd5e1;">
                        <p style="margin: 5px 0; font-size: 12px; color: #64748b;">📅 البداية: {s_date} | الانتهاء: {e_date}</p>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.error("❌ فشل أو لا يوجد اشتراك لهذا التطبيق")

with st.sidebar.popover("🔄 تجديد اشتراك التطبيق", use_container_width=True):
    st.markdown("<b style='color:#0f1c2e;'>🔄 تجديد اشتراك (تطبيق/إضافة)</b>", unsafe_allow_html=True)
    if current_sub and current_sub.get("id"):
        st.info(f"💡 سيتم تجديد الاشتراك رقم: **{current_sub.get('id')}** للباقة (**{current_sub.get('plan_name')}**) تلقائياً.")
        if st.button("تجديد الآن", key="btn_sub_renew", use_container_width=True, type="primary"):
            headers = {"Authorization": f"Bearer {st.session_state.get('access_token')}"}
            with st.spinner("⏳"):
                res = safe_api_request("POST", f"https://api.salla.dev/admin/v2/apps/subscriptions/{current_sub.get('id')}/renew", headers, json={})
                if res: st.success("✅ تم التجديد بنجاح!")
                else: st.error("❌ فشل التجديد")
    else:
        st.warning("⚠️ لا يوجد اشتراك ساري ليتم تجديده.")

with st.sidebar.popover("💰 تحديث رصيد الاستهلاك", use_container_width=True):
    st.markdown("<b style='color:#0f1c2e;'>💰 تحديث رصيد الاستهلاك</b>", unsafe_allow_html=True)
    st.info("💡 هذا الرصيد يُستخدم للتطبيقات التي تعتمد على باقات الدفع حسب الاستهلاك (Pay As You Go).")
    
    # ✅ وضع الرصيد الحالي للتاجر كقيمة افتراضية (أو 0 إذا لم يوجد)
    try: default_balance = int(float(balance_display))
    except: default_balance = 0
        
    balance_val = st.number_input("الرصيد الجديد:", min_value=0, value=default_balance, step=10, key="balance_input")
    
    if st.button("تحديث الرصيد", key="btn_sub_balance", use_container_width=True, type="primary"):
        headers = {"Authorization": f"Bearer {st.session_state.get('access_token')}"}
        with st.spinner("⏳"):
            res = safe_api_request("POST", "https://api.salla.dev/admin/v2/apps/balance", headers, json={"balance": int(balance_val)})
            if res: 
                st.success("✅ تم التحديث بنجاح!")
                if current_sub: st.session_state["app_subscription_data"]["subscription_balance"] = int(balance_val)
                import time; time.sleep(1); st.rerun()
            else: st.error("❌ فشل التحديث")

with st.sidebar.popover("⚙️ إعدادات التطبيق (Settings)", use_container_width=True):
    st.markdown("<b style='color:#0f1c2e;'>⚙️ إدارة إعدادات التطبيق</b>", unsafe_allow_html=True)
    st.info("💡 يتم عرض الإعدادات كحقول ديناميكية ذكية لتسهيل التعديل. يجب حفظ التغييرات لاعتمادها في المتجر.")

    # 1. زر الاستعلام
    if st.button("🔍 عرض تفاصيل الإعدادات", key="btn_get_settings", use_container_width=True):
        headers = {"Authorization": f"Bearer {st.session_state.get('access_token')}"}
        with st.spinner("⏳"):
            res = safe_api_request("GET", f"https://api.salla.dev/admin/v2/apps/{FIXED_APP_ID}/settings", headers)
            if res and res.get("data"):
                st.success("✅ تم جلب الإعدادات بنجاح!")
                st.session_state["app_settings_data"] = res["data"].get("settings", {})
                st.rerun()
            else:
                st.error("❌ لا توجد إعدادات. (تأكد من إنشاء نموذج الإعدادات في بوابة مطوري سلة)")
                if "app_settings_data" in st.session_state:
                    del st.session_state["app_settings_data"]

    # 2. عرض الحقول بشكل ديناميكي وجمالي
    if "app_settings_data" in st.session_state:
        st.markdown("<hr style='margin: 15px 0; border-top: 2px solid #00EBCF;'>", unsafe_allow_html=True)
        st.markdown("<b style='color:#0f1c2e;'>✏️ تعديل قيم الإعدادات:</b>", unsafe_allow_html=True)

        settings_data = st.session_state["app_settings_data"]
        updated_settings = {}

        if not settings_data:
            st.warning("لا توجد بيانات إعدادات محفوظة حالياً لهذا التطبيق.")
        else:
            with st.container(border=True):
                for key, val in settings_data.items():
                    if isinstance(val, bool):
                        updated_settings[key] = st.toggle(f"🔘 {key}", value=val, key=f"set_bool_{key}")
                    elif isinstance(val, int) and not isinstance(val, bool):
                        updated_settings[key] = st.number_input(f"🔢 {key}", value=val, step=1, key=f"set_int_{key}")
                    elif isinstance(val, float):
                        updated_settings[key] = st.number_input(f"🔢 {key}", value=val, step=0.1, key=f"set_float_{key}")
                    else:
                        is_pwd = "password" in str(key).lower() or "secret" in str(key).lower()
                        updated_settings[key] = st.text_input(f"📝 {key}", value=str(val) if val is not None else "", type="password" if is_pwd else "default", key=f"set_str_{key}")

            st.markdown("<br>", unsafe_allow_html=True)
            # 3. زر التحديث
            if st.button("💾 تحديث الإعدادات للمتجر", key="btn_update_settings", use_container_width=True, type="primary"):
                headers = {"Authorization": f"Bearer {st.session_state.get('access_token')}"}
                with st.spinner("⏳ جاري الحفظ..."):
                    res = safe_api_request("POST", f"https://api.salla.dev/admin/v2/apps/{FIXED_APP_ID}/settings", headers, json=updated_settings)
                    if res:
                        st.success("✅ تم تحديث الإعدادات بنجاح!")
                        st.session_state["app_settings_data"] = updated_settings 
                        import time; time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ فشل تحديث الإعدادات")

st.sidebar.markdown("<div style='margin-bottom: 15px;'></div>", unsafe_allow_html=True)
# ==========================================

page = st.sidebar.radio("القائمة الرئيسية", ["مركز إدارة المنتجات", "لوحة إدارة العروض الخاصة الحالية", "تفاصيل طلبات المتجر", "مركز إدارة العملاء والمجموعات"], label_visibility="collapsed")
st.sidebar.divider()

if st.sidebar.button("🔄 إعادة مزامنة البيانات", type="primary", use_container_width=True):
    # Get the newest token from central storage. Never read GitHub stores.json.
    curr_m = str(st.session_state.get("merchant_id") or "")
    if curr_m:
        try:
            latest = get_store(curr_m)
            if latest and latest.get("access_token"):
                st.session_state["access_token"] = latest["access_token"]
        except RuntimeError as exc:
            st.error(str(exc))
            st.stop()

    # 2. تفريغ كاش المتجر والباقة
    cache = get_global_store_cache()
    token = st.session_state.get('access_token', '')
    if token in cache:
        del cache[token]
    st.session_state.pop("app_subscription_data", None)
    st.session_state.pop("all_products_fetched", None)
    st.session_state.pop("all_products", None)
        
    if token:
        perform_initial_sync_with_ui({"Authorization": f"Bearer {token}"})
    st.rerun()

if st.sidebar.button("🚪 تسجيل الخروج", use_container_width=True, type="primary"):
    st.session_state["logged_in"] = False
    st.rerun()

if page == "مركز إدارة المنتجات": render_products_page()
elif page == "لوحة إدارة العروض الخاصة الحالية": render_offers_page()
elif page == "تفاصيل طلبات المتجر": render_orders_page()
elif page == "مركز إدارة العملاء والمجموعات": render_customers_page()
