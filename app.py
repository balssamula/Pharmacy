import streamlit as st
import os
import base64
import requests
from datetime import datetime, timedelta
# ✅ استيراد الدوال من utils
from utils import (
    get_headers, 
    safe_api_request, 
    get_branches_list,
    safe_parse_date,
    SALLA_API_URL
)

st.set_page_config(
    page_title="منظومة إدارة المنتجات والعروض الخاصة",
    layout="wide",
    page_icon="🎁",
    initial_sidebar_state="expanded"
)

from offers_page import render_offers_page
from products_page import render_products_page
from customers_page import render_customers_page

# ==========================================
# 📊 دوال التحميل مع شريط تقدم
# ==========================================

def fetch_products_with_progress(headers):
    """جلب المنتجات مع شريط تقدم وعداد"""
    products = []
    page = 1
    res = safe_api_request("GET", "https://api.salla.dev/admin/v2/products?per_page=60&page=1", headers)
    if not res: return []
    total_pages = res.get("pagination", {}).get("totalPages", 1)
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    while page <= total_pages:
        status_text.info(f"📦 جاري سحب المنتجات: صفحة {page} من {total_pages} | تم تحميل {len(products)} عنصر")
        res = safe_api_request("GET", f"https://api.salla.dev/admin/v2/products?per_page=60&page={page}", headers)
        if res and res.get("data"):
            products.extend(res["data"])
        progress_bar.progress(page / total_pages)
        page += 1
        
    progress_bar.empty()
    status_text.empty()
    return products

def fetch_offers_with_progress(headers):
    """جلب العروض مع شريط تقدم"""
    offers = []
    page = 1
    total_pages = 1
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    while True:
        status_text.info(f"🎁 جاري سحب العروض: صفحة {page} من {total_pages if page > 1 else '...'} | تم تحميل {len(offers)} عرض")
        res = safe_api_request("GET", f"https://api.salla.dev/admin/v2/specialoffers?per_page=60&page={page}", headers)
        if not res or not res.get("data"):
            break
        if page == 1:
            total_pages = res.get("pagination", {}).get("totalPages", 1)
        offers.extend(res["data"])
        progress_bar.progress(min(page / total_pages, 1.0))
        if page >= total_pages:
            break
        page += 1
        
    progress_bar.empty()
    status_text.empty()
    return offers

def build_product_offers_map_with_progress(offers, headers):
    """بناء خريطة المنتجات بالعروض مع شريط تقدم"""
    po_map = {}
    active_offers = [o for o in offers if o.get("status") == "active"]
    
    if not active_offers:
        return po_map
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    total = len(active_offers)
    
    for idx, o in enumerate(active_offers):
        status_text.info(f"🔗 جاري بناء روابط المنتجات بالعروض: {idx + 1} من {total}")
        oid = o.get("id")
        full_o = safe_api_request("GET", f"https://api.salla.dev/admin/v2/specialoffers/{oid}", headers)
        if full_o and full_o.get("data"):
            pids = set()
            for px in full_o["data"].get("buy", {}).get("products", []):
                pid = str(px.get("id", px) if isinstance(px, dict) else px)
                if pid.isdigit(): 
                    pids.add(pid)
            for px in full_o["data"].get("get", {}).get("products", []):
                pid = str(px.get("id", px) if isinstance(px, dict) else px)
                if pid.isdigit(): 
                    pids.add(pid)
            for pid in pids:
                if pid not in po_map:
                    po_map[pid] = []
                po_map[pid].append({"id": oid, "name": o.get("name")})
        progress_bar.progress((idx + 1) / total)
    
    progress_bar.empty()
    status_text.empty()
    return po_map

def load_all_data_with_progress():
    """تحميل جميع البيانات مع شريط تقدم"""
    headers = get_headers()
    if not headers:
        return None
    
    st.markdown("### ⏳ جاري تحميل بيانات المتجر...")
    
    # 1. جلب المنتجات
    products = fetch_products_with_progress(headers)
    
    # 2. جلب العروض
    offers = fetch_offers_with_progress(headers)
    
    # 3. جلب الفروع
    status_text = st.empty()
    status_text.info("🏢 جاري سحب الفروع...")
    branches = get_branches_list()
    status_text.empty()
    
    # 4. بناء روابط المنتجات بالعروض
    po_map = build_product_offers_map_with_progress(offers, headers)
    
    # ✅ عرض رسالة نجاح مؤقتة
    success_msg = st.success(f"✅ تم تحميل {len(products)} منتج و {len(offers)} عرض و {len(branches)} فرع بنجاح!")
    import time
    time.sleep(2)
    success_msg.empty()
    
    return {
        "products": products,
        "offers": offers,
        "branches": branches,
        "product_offers_map": po_map,
        "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

# ==========================================
# 💾 دوال التخزين المؤقت
# ==========================================

@st.cache_data(ttl=3600, show_spinner=False)
def get_cached_data_without_spinner():
    """جلب البيانات مع التخزين المؤقت (بدون عرض شريط تقدم)"""
    headers = get_headers()
    if not headers:
        return None
    
    # جلب سريع للبيانات
    products = []
    page = 1
    while True:
        res = safe_api_request("GET", f"https://api.salla.dev/admin/v2/products?per_page=100&page={page}", headers)
        if not res or not res.get("data"):
            break
        products.extend(res["data"])
        if page >= res.get("pagination", {}).get("totalPages", 1):
            break
        page += 1
    
    offers = []
    page = 1
    while True:
        res = safe_api_request("GET", f"https://api.salla.dev/admin/v2/specialoffers?per_page=100&page={page}", headers)
        if not res or not res.get("data"):
            break
        offers.extend(res["data"])
        if page >= res.get("pagination", {}).get("totalPages", 1):
            break
        page += 1
    
    branches = get_branches_list()
    
    # ✅ بناء خريطة العروض
    po_map = {}
    for o in offers:
        if o.get("status") != "active":
            continue
        oid = o.get("id")
        full_o = safe_api_request("GET", f"https://api.salla.dev/admin/v2/specialoffers/{oid}", headers)
        if full_o and full_o.get("data"):
            pids = set()
            for px in full_o["data"].get("buy", {}).get("products", []):
                pid = str(px.get("id", px) if isinstance(px, dict) else px)
                if pid.isdigit():
                    pids.add(pid)
            for px in full_o["data"].get("get", {}).get("products", []):
                pid = str(px.get("id", px) if isinstance(px, dict) else px)
                if pid.isdigit():
                    pids.add(pid)
            for pid in pids:
                if pid not in po_map:
                    po_map[pid] = []
                po_map[pid].append({"id": oid, "name": o.get("name")})
    
    return {
        "products": products,
        "offers": offers,
        "branches": branches,
        "product_offers_map": po_map,
        "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

# ==========================================
# 🚀 دوال التحميل والتهيئة
# ==========================================

def preload_data():
    """تحميل البيانات مسبقاً مع شريط تقدم في حالة عدم وجود كاش"""
    if st.session_state.get("all_products_fetched", False):
        return True
    
    # ✅ أولاً: التحقق من وجود بيانات في الكاش
    cached_data = get_cached_data_without_spinner()
    
    if cached_data:
        # ✅ البيانات موجودة في الكاش، استخدمها مباشرة
        st.session_state["all_products"] = cached_data["products"]
        st.session_state["all_offers"] = cached_data["offers"]
        st.session_state["branches"] = cached_data["branches"]
        st.session_state["product_offers_map"] = cached_data["product_offers_map"]
        st.session_state["all_products_fetched"] = True
        st.session_state["last_sync_time"] = cached_data["fetched_at"]
        return True
    else:
        # ✅ لا يوجد كاش، قم بتحميل البيانات مع شريط تقدم
        data = load_all_data_with_progress()
        if data:
            st.session_state["all_products"] = data["products"]
            st.session_state["all_offers"] = data["offers"]
            st.session_state["branches"] = data["branches"]
            st.session_state["product_offers_map"] = data["product_offers_map"]
            st.session_state["all_products_fetched"] = True
            st.session_state["last_sync_time"] = data["fetched_at"]
            return True
    return False

def initialize_global_products():
    """تهيئة المنتجات بشكل عام لجميع الصفحات"""
    if "all_products" not in st.session_state:
        st.session_state["all_products"] = []
    if "all_products_fetched" not in st.session_state:
        st.session_state["all_products_fetched"] = False
    if "last_sync_time" not in st.session_state:
        st.session_state["last_sync_time"] = None
    if "product_offers_map" not in st.session_state:
        st.session_state["product_offers_map"] = {}
    if "branches" not in st.session_state:
        st.session_state["branches"] = []

def fetch_all_pages(url_base, headers):
    """جلب جميع الصفحات من API (بدون شريط تقدم)"""
    all_data = []
    page = 1
    
    while True:
        url = f"{url_base}?per_page=60&page={page}" if "?" not in url_base else f"{url_base}&per_page=60&page={page}"
        res = safe_api_request("GET", url, headers)
        if not res or not res.get("data"):
            break
        all_data.extend(res["data"])
        if page >= res.get("pagination", {}).get("totalPages", 1):
            break
        page += 1
    
    return all_data

# ==========================================
# 🎯 زر تحميل روابط المنتجات بالعروض
# ==========================================

def rebuild_product_offers_mapping():
    """إعادة بناء روابط المنتجات بالعروض الخاصة مع شريط تقدم"""
    headers = get_headers()
    if not headers:
        st.error("⚠️ الرجاء تسجيل الدخول أولاً")
        return
    
    if not st.session_state.get("all_offers"):
        st.warning("⚠️ لا توجد عروض محملة. قم بتحديث البيانات أولاً.")
        return
    
    with st.spinner("🔄 جاري بناء روابط المنتجات بالعروض الخاصة..."):
        po_map = build_product_offers_map_with_progress(
            st.session_state.get("all_offers", []), 
            headers
        )
        st.session_state["product_offers_map"] = po_map
        st.success(f"✅ تم بناء روابط {len(po_map)} منتج بالعروض الخاصة!")
        st.rerun()

# ==========================================
# 🎨 CSS
# ==========================================
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
    
    html, body, .stApp, h1, h2, h3, h4, h5, h6, p, label, input, select, textarea,
    div[data-testid="stMarkdownContainer"] p, div.stSelectbox div {
        font-family: 'Cairo', sans-serif !important;
    }
    
    .stIcon, [data-testid="stIcon"], [class^="st-"] svg, svg, i,
    span[data-testid="stIconVisibility"], summary svg, button svg,
    [data-base-ui="icon"], [class*="Icon"], summary::after,
    .st-emotion-cache-p6w706, .st-emotion-cache-1n76uvr, [data-testid="stExpander"] svg {
        font-family: inherit !important;
    }
    
    div.stButton > button[data-testid="baseButton-primary"] {
        background-color: #0f5132 !important;
        color: #ffffff !important;
        border: 1px solid #0f5132 !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.08) !important;
        font-size: 14px !important;
        font-family: 'Cairo', sans-serif !important;
    }
    div.stButton > button[data-testid="baseButton-primary"]:hover {
        background-color: #146c43 !important;
        border-color: #146c43 !important;
        transform: scale(1.02) !important;
    }
    
    div[data-testid="stPopover"] button {
        background-color: #0f5132 !important;
        color: #ffffff !important;
        border-radius: 8px !important;
    }
    
    div.stButton > button[key*="t_dl_"] {
        background-color: #dc3545 !important;
        color: #ffffff !important;
        border: 1px solid #dc3545 !important;
    }
    
    [data-testid="stSidebar"] { background-color: #0f1c2e !important; padding: 20px 15px !important; }
    [data-testid="stSidebar"] * { color: #ffffff !important; }
    .stButton button { border-radius: 8px !important; font-weight: 600 !important; }
    
    [data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child {
        display: none !important;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] label > div:nth-child(2) {
        width: 100% !important;
        margin: 0 !important;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] label {
        background: linear-gradient(135deg, #1E293B 0%, #0F1C2E 100%);
        padding: 14px 15px !important;
        margin-bottom: 16px !important;
        border-radius: 8px !important;
        transform: skewX(-12deg);
        border: 1px solid #334155;
        position: relative;
        overflow: hidden;
        transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        cursor: pointer;
        display: flex;
        align-items: center;
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        width: 92% !important;
        margin-left: auto !important;
        margin-right: auto !important;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] label div[data-testid="stMarkdownContainer"] {
        transform: skewX(12deg);
        text-align: center;
        width: 100%;
        position: relative;
        z-index: 2;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] label div[data-testid="stMarkdownContainer"] p {
        color: #94A3B8 !important;
        font-weight: 700 !important;
        font-size: 15px !important;
        margin: 0 !important;
        transition: all 0.3s ease;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] label::after {
        content: '';
        position: absolute;
        left: -15px;
        top: 0;
        bottom: 0;
        width: 45px;
        background: repeating-linear-gradient(
            45deg,
            rgba(255,255,255,0.03),
            rgba(255,255,255,0.03) 4px,
            transparent 4px,
            transparent 8px
        );
        transform: skewX(12deg);
        border-right: 2px solid rgba(255,255,255,0.05);
        z-index: 1;
        transition: all 0.3s ease;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] label:hover {
        background: linear-gradient(135deg, #2D3748 0%, #1E293B 100%);
        border-color: #00EBCF;
        transform: skewX(-12deg) scale(1.02);
    }
    [data-testid="stSidebar"] div[role="radiogroup"] label:hover div[data-testid="stMarkdownContainer"] p {
        color: #00EBCF !important;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {
        background: linear-gradient(135deg, #00EBCF 0%, #0284C7 100%) !important;
        border-color: #00EBCF !important;
        box-shadow: 0 0 20px rgba(0, 235, 207, 0.4) !important;
        transform: skewX(-12deg) scale(1.06) !important;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) div[data-testid="stMarkdownContainer"] p {
        color: #FFFFFF !important;
        text-shadow: 1px 1px 3px rgba(0,0,0,0.4) !important;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked)::after {
        background: repeating-linear-gradient(
            45deg,
            rgba(255,255,255,0.2),
            rgba(255,255,255,0.2) 4px,
            transparent 4px,
            transparent 8px
        );
        border-right: 2px solid rgba(255,255,255,0.4);
    }
    .blinking-dot {
        height: 12px;
        width: 12px;
        background-color: #10B981;
        border-radius: 50%;
        display: inline-block;
        box-shadow: 0 0 8px #10B981;
        animation: blinker 1.5s linear infinite;
    }
    @keyframes blinker {
        50% { opacity: 0.3; box-shadow: 0 0 2px #10B981; }
    }
    
    /* ✅ تنسيق الزر الجديد */
    .stButton > button[key="rebuild_offers_mapping"] {
        background: linear-gradient(135deg, #f7971e 0%, #ffd200 100%) !important;
        color: #1a1a2e !important;
        font-weight: 700 !important;
        border: none !important;
        box-shadow: 0 4px 15px rgba(255, 215, 0, 0.3) !important;
    }
    .stButton > button[key="rebuild_offers_mapping"]:hover {
        transform: scale(1.02) !important;
        box-shadow: 0 6px 25px rgba(255, 215, 0, 0.5) !important;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 🔐 تسجيل الدخول
# ==========================================

if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if "access_token" not in st.session_state: st.session_state["access_token"] = ""
if "admin_password" not in st.session_state: st.session_state["admin_password"] = "admin123"
if "store_name" not in st.session_state: st.session_state["store_name"] = "متجر سلة"
if "login_time" not in st.session_state: st.session_state["login_time"] = ""

if not st.session_state["logged_in"]:
    _, col2, _ = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h3 style='text-align:center;'>🏥 تسجيل الدخول - مدير المنتجات والعروض الخاصة الذكي</h3>", unsafe_allow_html=True)
        st.divider()
        token = st.text_input("🔑 مفتاح الربط (Access Token):", type="password")
        un = st.text_input("👤 اسم المستخدم:")
        pw = st.text_input("🔒 كلمة المرور:", type="password")
        if st.button("🚀 دخول آمن للمنظومة", use_container_width=True, type="primary"):
            if un == "admin" and pw == st.session_state["admin_password"] and token.strip():
                with st.spinner("جاري التحقق والاتصال بمتجرك..."):
                    try:
                        headers = {"Authorization": f"Bearer {token.strip()}"}
                        res = requests.get("https://api.salla.dev/admin/v2/store/info", headers=headers, timeout=10)
                        if res.status_code < 400:
                            st.session_state["store_name"] = res.json().get("data", {}).get("name", "متجر سلة")
                    except Exception:
                        pass
                    
                    ksa_time = datetime.now() + timedelta(hours=3)
                    st.session_state["login_time"] = ksa_time.strftime("%Y-%m-%d %I:%M %p")
                    st.session_state["logged_in"] = True
                    st.session_state["access_token"] = token.strip()
                    
                    # ✅ تحميل البيانات بعد تسجيل الدخول
                    preload_data()
                    
                    st.rerun()
            else:
                st.error("❌ عذراً، تأكد من صحة البيانات والتوكن المرفق!")
    st.stop()

# ==========================================
# 🏠 الواجهة الرئيسية
# ==========================================

st.markdown("""
<div style="background: linear-gradient(135deg, #1E293B 0%, #3B82F6 100%); padding: 25px; border-radius: 12px; color: white; text-align: center; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
    <h1 style="color: white; margin: 0; font-size: 2.2rem;">🎁 منظومة إدارة المنتجات والعروض الخاصة</h1>
    <p style="margin: 5px 0 0 0; opacity: 0.9; font-size: 1.1rem;">تحكم كامل وسريع بمتجرك على منصة سلة</p>
</div>
""", unsafe_allow_html=True)

st.markdown("---")

c_tok, c_pwd, _ = st.columns([2, 2, 4])
with c_tok:
    with st.popover("⚙️ إعدادات مفتاح الربط"):
        st.markdown("<div style='background:#f8fafc; padding:10px; border-radius:8px; border-right:4px solid #3B82F6;'>تحديث توكن الاتصال بمنصة سلة</div>", unsafe_allow_html=True)
        new_t = st.text_input("أدخل توكن الربط الجديد:", value=st.session_state["access_token"], type="password")
        if st.button("تحديث التوكن والربط", type="primary", use_container_width=True):
            st.session_state["access_token"] = new_t
            st.success("تم التحديث!")
            st.rerun()
with c_pwd:
    with st.popover("🔒 تعديل كلمة مرور النظام"):
        st.markdown("<div style='background:#f8fafc; padding:10px; border-radius:8px; border-right:4px solid #10B981;'>تحديث كلمة مرور الدخول للوحة</div>", unsafe_allow_html=True)
        new_p = st.text_input("أدخل الباسورد الجديد:", type="password")
        if st.button("حفظ الباسورد الجديد", type="primary", use_container_width=True):
            st.session_state["admin_password"] = new_p
            st.success("تم الحفظ بنجاح!")

st.divider()

# ==========================================
# 📌 القائمة الجانبية
# ==========================================

st.sidebar.markdown(f"""
<div style="background: linear-gradient(135deg, #0F1C2E, #1a365d); padding: 20px 15px; border-radius: 12px; border: 1px solid #334155; margin-bottom: 25px; box-shadow: 0 4px 10px rgba(0,0,0,0.2);">
    <div style="text-align: center; margin-bottom: 12px;">
        <div style="font-size: 32px; margin-bottom: 5px;">🏪</div>
        <h3 style="color: #FFFFFF; margin: 0; font-family: 'Cairo', sans-serif; font-size: 18px; text-shadow: 1px 1px 2px rgba(0,0,0,0.5);">{st.session_state.get('store_name', 'متجرك')}</h3>
    </div>
    <div style="background: rgba(0,0,0,0.2); border-radius: 8px; padding: 10px;">
        <div style="display: flex; align-items: center; justify-content: center; font-size: 14px; margin-bottom: 8px; gap: 8px;">
            <span class="blinking-dot"></span>
            <span style="color: #10B981; font-weight: bold;">متصل ومزامن لحظياً</span>
        </div>
        <div style="text-align: center; font-size: 12px; color: #94A3B8; border-top: 1px dashed #334155; padding-top: 8px; margin-top: 5px;">
            آخر دخول: <b style="color: #CBD5E1; direction: ltr; display: inline-block;">{st.session_state.get('login_time', '')}</b>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# أزرار القائمة الجانبية
page = st.sidebar.radio(
    "القائمة الرئيسية",
    ["مركز إدارة المنتجات", "لوحة إدارة العروض الخاصة الحالية", "مركز إدارة العملاء والمجموعات"],
    label_visibility="collapsed"
)

st.sidebar.divider()

# ✅ زر تحديث البيانات
if st.sidebar.button("🔄 تحديث البيانات", use_container_width=True, type="primary"):
    st.rerun()

# ✅ ✅ ✅ زر جديد: تحميل روابط المنتجات بالعروض الخاصة
st.sidebar.markdown("---")
st.sidebar.markdown("### 🔗 روابط العروض")
if st.sidebar.button("🔗 تحميل روابط المنتجات بالعروض الخاصة", use_container_width=True, key="rebuild_offers_mapping"):
    rebuild_product_offers_mapping()

col_refresh1, col_refresh2 = st.sidebar.columns(2)
with col_refresh1:
    if st.sidebar.button("🔄 تحديث الكل", type="primary", use_container_width=True):
        st.cache_data.clear()
        st.session_state["all_products_fetched"] = False
        with st.spinner("⏳ جاري تحديث البيانات..."):
            preload_data()
        st.rerun()

with col_refresh2:
    if st.sidebar.button("🚪 خروج", use_container_width=True, type="primary"):
        st.session_state["logged_in"] = False
        st.rerun()

# في القائمة الجانبية - عرض حالة البيانات
if st.session_state.get("all_products_fetched", False):
    st.sidebar.success(f"✅ {len(st.session_state.get('all_products', []))} منتج")
    st.sidebar.info(f"🕐 {st.session_state.get('last_sync_time', '')}")
    
    # ✅ عرض عدد الروابط
    po_map = st.session_state.get("product_offers_map", {})
    if po_map:
        st.sidebar.info(f"🔗 {len(po_map)} منتج مرتبط بعروض")
    else:
        st.sidebar.warning("⚠️ لا توجد روابط عروض")
else:
    st.sidebar.warning("⏳ جاري التحميل...")
    
# ==========================================
# 📄 عرض الصفحات
# ==========================================

if page == "مركز إدارة المنتجات":
    render_products_page()
elif page == "لوحة إدارة العروض الخاصة الحالية":
    render_offers_page()
elif page == "مركز إدارة العملاء والمجموعات":
    render_customers_page()

# ==========================================
# 🌐 المزامنة الموحدة
# ==========================================

def perform_unified_sync():
    """مزامنة موحدة لجميع الصفحات (تتم مرة واحدة فقط)"""
    headers = get_headers()
    if not headers:
        return
    
    if st.session_state.get("sync_in_progress", False):
        return
    
    if st.session_state.get("all_products_fetched", False):
        return
    
    st.session_state["sync_in_progress"] = True
    
    with st.spinner("⏳ جاري المزامنة الشاملة للمنتجات والعروض..."):
        try:
            all_p = []
            page = 1
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            while True:
                res = safe_api_request("GET", f"https://api.salla.dev/admin/v2/products?per_page=60&page={page}", headers)
                if not res or not res.get("data"):
                    break
                all_p.extend(res["data"])
                total_pages = res.get("pagination", {}).get("totalPages", 1)
                progress_bar.progress(page / total_pages)
                status_text.info(f"📥 تحميل المنتجات: صفحة {page} من {total_pages} | تم تحميل {len(all_p)} منتج")
                if page >= total_pages:
                    break
                page += 1
            
            st.session_state["all_products"] = all_p
            progress_bar.empty()
            status_text.empty()
            
            st.session_state["branches"] = get_branches_list()
            st.session_state["all_categories"] = fetch_all_pages("https://api.salla.dev/admin/v2/categories", headers)
            st.session_state["all_brands"] = fetch_all_pages("https://api.salla.dev/admin/v2/brands", headers)
            
            all_o = fetch_all_pages(SALLA_API_URL, headers)
            st.session_state["all_offers"] = all_o
            
            # ✅ بناء خريطة العروض
            po_map = build_product_offers_map_with_progress(all_o, headers)
            st.session_state["product_offers_map"] = po_map
            st.session_state["all_products_fetched"] = True
            st.session_state["last_sync_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.session_state["sync_in_progress"] = False
            
            st.success(f"✅ تمت المزامنة الشاملة! ({len(all_p)} منتج، {len(all_o)} عرض)")
            st.rerun()
            
        except Exception as e:
            st.session_state["sync_in_progress"] = False
            st.error(f"❌ فشل المزامنة: {str(e)}")

def get_alert_sound_base64():
    """قراءة ملف الصوت وتحويله إلى base64"""
    sound_path = os.path.join(os.path.dirname(__file__), "alert.wav")
    if os.path.exists(sound_path):
        with open(sound_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return None

# ✅ بعد نجاح تسجيل الدخول
if st.session_state.get("logged_in", False):
    # ✅ تحميل البيانات في الخلفية
    preload_data()
