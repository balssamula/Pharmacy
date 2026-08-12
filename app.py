import streamlit as st
import requests
import json
import os
import base64
import time
from datetime import datetime, timedelta
from utils import get_headers, safe_api_request, get_branches_list
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
    
    if token in cache and (now - cache[token]['time']).total_seconds() < 86400:
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
        tp_safe = min(tp, 100)
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
    time.sleep(1.5)
    
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
if "admin_username" not in st.session_state: st.session_state["admin_username"] = "admin"
if "admin_password" not in st.session_state: st.session_state["admin_password"] = "admin123"

# --- الشاشة الأولى: تسجيل دخول المدير ---
if not st.session_state["is_admin_logged_in"]:
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    _, col_login, _ = st.columns([1, 1.5, 1])
    
    with col_login:
        with st.container(border=True):
            st.markdown("<h2 style='text-align:center; color:#00EBCF; margin-bottom: 20px;'>👑 الإدارة المركزية للتطبيقات</h2>", unsafe_allow_html=True)
            
            un = st.text_input("👤 اسم المستخدم الإداري:")
            pw = st.text_input("🔒 كلمة المرور:", type="password")
            
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🚀 تسجيل الدخول للوحة التحكم", use_container_width=True, type="primary"):
                if un == st.session_state["admin_username"] and pw == st.session_state["admin_password"]:
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
    
    # 1. قراءة المتاجر المربوطة من قاعدة البيانات (أو ملف JSON)
    stores_db_path = "stores.json"
    if os.path.exists(stores_db_path):
        with open(stores_db_path, "r", encoding="utf-8") as f:
            connected_stores = json.load(f)
    else:
        connected_stores = []
        st.warning("⚠️ ملف قاعدة بيانات المتاجر (stores.json) غير موجود!")

    # 2. عرض المتاجر كبطاقات إدارية
    if connected_stores:
        cols = st.columns(3) # عرض المتاجر في 3 أعمدة
        for idx, store in enumerate(connected_stores):
            with cols[idx % 3]:
                with st.container(border=True):
                    st.markdown(f"""
                    <h3 style='color:#00EBCF; margin-bottom:5px; text-align:center;'>🏪 {store.get('store_name')}</h3>
                    <div style='text-align:center; font-size:13px; color:#94A3B8; margin-bottom:15px;'>
                        <b>رقم التاجر:</b> {store.get('merchant_id')}<br>
                        <b>تاريخ الربط:</b> {store.get('installed_at')}
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # زر تسجيل الدخول التلقائي لهذا المتجر بالذات
                    if st.button(f"🔑 إدارة هذا المتجر", key=f"login_store_{store.get('merchant_id')}", use_container_width=True, type="primary"):
                        # تعيين التوكن في الجلسة المخفية
                        token = store.get("access_token")
                        headers = {"Authorization": f"Bearer {token}"}
                        
                        # 🚀 استدعاء المزامنة الحية المدمجة لتهيئة البيانات
                        perform_initial_sync_with_ui(headers)
                        
                        # تفعيل حالة الدخول للانتقال للتطبيق
                        st.session_state["store_name"] = store.get('store_name')
                        st.session_state["logged_in"] = True
                        st.session_state["access_token"] = token
                        ksa_time = datetime.now() + timedelta(hours=3)
                        st.session_state["login_time"] = ksa_time.strftime("%Y-%m-%d %I:%M %p")
                        
                        st.rerun()
    else:
        st.info("لم يقم أي تاجر بتثبيت التطبيق حتى الآن.")

    # زر تسجيل الخروج للمدير
    st.divider()
    if st.button("🚪 تسجيل الخروج من حساب المدير", type="secondary"):
        st.session_state["is_admin_logged_in"] = False
        st.rerun()
        
    st.stop() # إيقاف الكود هنا حتى يختار المدير متجراً

# ==========================================
# 🏠 الواجهة الرئيسية (بعد اختيار المتجر)
# ==========================================
st.markdown("""
<div style="background: linear-gradient(135deg, #1E293B 0%, #3B82F6 100%); padding: 25px; border-radius: 12px; color: white; text-align: center; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
    <h1 style="color: white; margin: 0; font-size: 2.2rem;">🎁 منظومة إدارة المنتجات والعروض الخاصة</h1>
</div>
""", unsafe_allow_html=True)

# ✅ جلب معرف التطبيق المحفوظ ليعرض في الأعلى
saved_app_id = st.session_state.get("saved_app_id", "لم يحدد بعد")

st.sidebar.markdown(f"""
<div style="background: linear-gradient(135deg, #0F1C2E, #1a365d); padding: 20px 15px; border-radius: 12px; border: 1px solid #334155; margin-bottom: 25px; box-shadow: 0 4px 10px rgba(0,0,0,0.2); position: relative; overflow: hidden;">
    <div style="position: absolute; top: 0; right: 0; background: linear-gradient(90deg, #F59E0B, #D97706); color: #FFF; padding: 4px 12px; border-bottom-left-radius: 12px; font-weight: bold; font-size: 12px; box-shadow: -2px 2px 8px rgba(0,0,0,0.3); z-index: 10;">
        🆔 App ID: {saved_app_id}
    </div>
    <div style="text-align: center; margin-bottom: 12px; margin-top: 15px;">
        <div style="font-size: 32px; margin-bottom: 5px;">🏪</div>
        <h3 style="color: #FFFFFF; margin: 0; font-size: 18px;">{st.session_state.get('store_name', 'متجرك')}</h3>
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
# ✅ أزرار إدارة اشتراكات التطبيق (عرضية واحترافية)
# ==========================================

with st.sidebar.popover("📋 تفاصيل واشتراكات التطبيق", use_container_width=True):
    st.markdown("<b style='color:#0f1c2e;'>🔍 استعلام عن الاشتراك</b>", unsafe_allow_html=True)
    # ✅ بمجرد إدخال المعرف هنا سيتم حفظه ليظهر في الشارة العلوية
    app_id_val = st.text_input("معرف التطبيق (App ID):", value=st.session_state.get("saved_app_id", ""), key="app_id_input")
    if app_id_val != st.session_state.get("saved_app_id", ""):
        st.session_state["saved_app_id"] = app_id_val
        st.rerun()
        
    if st.button("استعلام", key="btn_sub_info", use_container_width=True, type="primary"):
        if not app_id_val:
            st.warning("الرجاء إدخال معرف التطبيق")
        else:
            headers = {"Authorization": f"Bearer {st.session_state.get('access_token')}"}
            with st.spinner("⏳"):
                res = safe_api_request("GET", f"https://api.salla.dev/admin/v2/apps/{app_id_val}/subscriptions", headers)
                if res and res.get("data"):
                    st.success("✅ جلب البيانات بنجاح!")
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
    sub_id_val = st.text_input("معرف الاشتراك:", key="sub_id_input")
    if st.button("تجديد الآن", key="btn_sub_renew", use_container_width=True, type="primary"):
        if not sub_id_val: st.warning("الرجاء إدخال معرف الاشتراك")
        else:
            headers = {"Authorization": f"Bearer {st.session_state.get('access_token')}"}
            with st.spinner("⏳"):
                res = safe_api_request("POST", f"https://api.salla.dev/admin/v2/apps/subscriptions/{sub_id_val}/renew", headers, json={})
                if res: st.success("✅ تم التجديد بنجاح!")
                else: st.error("❌ فشل التجديد")

with st.sidebar.popover("💰 تحديث رصيد الاستهلاك", use_container_width=True):
    st.markdown("<b style='color:#0f1c2e;'>💰 تحديث رصيد الاستهلاك</b>", unsafe_allow_html=True)
    st.info("💡 هذا الرصيد يُستخدم فقط للتطبيقات التي تعتمد على باقات الدفع حسب الاستهلاك (Pay As You Go).")
    balance_val = st.number_input("الرصيد الجديد:", min_value=0, value=0, step=10, key="balance_input")
    if st.button("تحديث الرصيد", key="btn_sub_balance", use_container_width=True, type="primary"):
        headers = {"Authorization": f"Bearer {st.session_state.get('access_token')}"}
        with st.spinner("⏳"):
            res = safe_api_request("POST", "https://api.salla.dev/admin/v2/apps/balance", headers, json={"balance": int(balance_val)})
            if res: st.success("✅ تم التحديث بنجاح!")
            else: st.error("❌ فشل التحديث")

st.sidebar.markdown("<div style='margin-bottom: 15px;'></div>", unsafe_allow_html=True)
# ==========================================

page = st.sidebar.radio("القائمة الرئيسية", ["مركز إدارة المنتجات", "لوحة إدارة العروض الخاصة الحالية", "مركز إدارة العملاء والمجموعات"], label_visibility="collapsed")
st.sidebar.divider()

if st.sidebar.button("🔄 إعادة مزامنة البيانات", type="primary", use_container_width=True):
    # ⚡ مسح الذاكرة المخبأة لهذا المتجر تحديداً لإجبار النظام على إظهار شريط التقدم وسحب البيانات الجديدة
    cache = get_global_store_cache()
    token = st.session_state['access_token']
    if token in cache:
        del cache[token]
        
    perform_initial_sync_with_ui({"Authorization": f"Bearer {token}"})
    st.rerun()

if st.sidebar.button("🚪 تسجيل الخروج", use_container_width=True, type="primary"):
    st.session_state["logged_in"] = False
    st.rerun()

if page == "مركز إدارة المنتجات": render_products_page()
elif page == "لوحة إدارة العروض الخاصة الحالية": render_offers_page()
elif page == "مركز إدارة العملاء والمجموعات": render_customers_page()
