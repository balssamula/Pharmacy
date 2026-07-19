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
# 🔄 المزامنة الحية فائقة السرعة (بدون حظر API)
# ==========================================
def perform_initial_sync_with_ui(headers):
    placeholder = st.empty()
    with placeholder.container():
        st.markdown("""
        <div style='background: #0F1C2E; padding: 20px; border-radius: 12px; border: 1px solid #00EBCF; text-align: center; margin-bottom: 20px;'>
            <h3 style='color: #00EBCF; margin: 0;'>🔄 جاري تهيئة المنظومة وسحب بيانات متجرك...</h3>
        </div>
        """, unsafe_allow_html=True)
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # 1. سحب المنتجات
        status_text.info("📦 جاري الاتصال وسحب المنتجات...")
        products = []
        res = safe_api_request("GET", "https://api.salla.dev/admin/v2/products?per_page=60&page=1", headers)
        if res:
            tp = res.get("pagination", {}).get("totalPages", 1)
            products.extend(res.get("data", []))
            for page in range(2, tp + 1):
                status_text.info(f"📦 جاري سحب المنتجات: صفحة {page} من {tp} | (تم تحميل {len(products)} منتج)")
                p_res = safe_api_request("GET", f"https://api.salla.dev/admin/v2/products?per_page=60&page={page}", headers)
                if p_res and p_res.get("data"): products.extend(p_res["data"])
                progress_bar.progress(0.4 * (page / tp))
        st.session_state["all_products"] = products
        
        # 2. سحب العروض
        status_text.info("🎁 جاري سحب العروض الخاصة النشطة...")
        offers = []
        o_res = safe_api_request("GET", "https://api.salla.dev/admin/v2/specialoffers?per_page=60&page=1", headers)
        if o_res:
            tp = o_res.get("pagination", {}).get("totalPages", 1)
            offers.extend(o_res.get("data", []))
            for page in range(2, tp + 1):
                status_text.info(f"🎁 جاري سحب العروض: صفحة {page} من {tp}")
                op_res = safe_api_request("GET", f"https://api.salla.dev/admin/v2/specialoffers?per_page=60&page={page}", headers)
                if op_res and op_res.get("data"): offers.extend(op_res["data"])
                progress_bar.progress(0.4 + (0.4 * (page / tp)))
        st.session_state["all_offers"] = offers
        
        # 3. بناء خريطة العروض (من الذاكرة بسرعة البرق لتجنب حظر سلة)
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
                buy_data = o.get("buy") or {}
                for px in buy_data.get("products", []):
                    pid = str(px.get("id", px) if isinstance(px, dict) else px)
                    if pid.isdigit(): pids.add(pid)
                    
                get_data = o.get("get") or {}
                for px in get_data.get("products", []):
                    pid = str(px.get("id", px) if isinstance(px, dict) else px)
                    if pid.isdigit(): pids.add(pid)
                    
                for px in o.get("products", []):
                    pid = str(px.get("id", px) if isinstance(px, dict) else px)
                    if pid.isdigit(): pids.add(pid)
                    
                for pid in pids:
                    if pid not in po_map: po_map[pid] = []
                    po_map[pid].append(summary)
                    
        st.session_state["product_offers_map"] = po_map
        progress_bar.progress(0.9)
        
        # 4. الفروع
        status_text.info("🏢 جاري جلب الفروع والمستودعات...")
        st.session_state["branches"] = get_branches_list()
        progress_bar.progress(1.0)
        
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
# 🔐 تسجيل الدخول (التصميم الاحترافي بـ Native Streamlit)
# ==========================================

if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if "admin_password" not in st.session_state: st.session_state["admin_password"] = "admin123"
if "access_token" not in st.session_state: st.session_state["access_token"] = ""
if "store_name" not in st.session_state: st.session_state["store_name"] = "متجر سلة"

if not st.session_state["logged_in"]:
    st.markdown("<br><br>", unsafe_allow_html=True)
    _, col_login, _ = st.columns([1, 1.5, 1])
    
    with col_login:
        # حاوية احترافية محددة الإطار من Streamlit بدلاً من HTML المكسور
        with st.container(border=True):
            st.markdown("<h2 style='text-align:center; color:#00EBCF; margin-bottom: 20px;'>🏥 مدير المنظومة الذكي</h2>", unsafe_allow_html=True)
            
            token = st.text_input("🔑 مفتاح الربط (Access Token):", type="password")
            un = st.text_input("👤 اسم المستخدم:")
            pw = st.text_input("🔒 كلمة المرور:", type="password")
            
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🚀 دخول آمن وبدء تهيئة البيانات", use_container_width=True, type="primary"):
                if un == "admin" and pw == st.session_state["admin_password"] and token.strip():
                    headers = {"Authorization": f"Bearer {token.strip()}"}
                    try:
                        res = requests.get("https://api.salla.dev/admin/v2/store/info", headers=headers, timeout=10)
                        if res.status_code < 400: st.session_state["store_name"] = res.json().get("data", {}).get("name", "متجر سلة")
                    except: pass
                    
                    # 🚀 استدعاء المزامنة الحية بشريط التقدم
                    perform_initial_sync_with_ui(headers)
                    
                    st.session_state["logged_in"] = True
                    st.session_state["access_token"] = token.strip()
                    st.rerun()
                else:
                    st.error("❌ تأكد من صحة اسم المستخدم وكلمة المرور ومفتاح الربط!")
    st.stop()

# ==========================================
# 🏠 الواجهة الرئيسية (بعد الدخول)
# ==========================================

st.markdown("""
<div style="background: linear-gradient(135deg, #1E293B 0%, #3B82F6 100%); padding: 25px; border-radius: 12px; color: white; text-align: center; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
    <h1 style="color: white; margin: 0; font-size: 2.2rem;">🎁 منظومة إدارة المنتجات والعروض الخاصة</h1>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown(f"""
<div style="background: linear-gradient(135deg, #0F1C2E, #1a365d); padding: 20px 15px; border-radius: 12px; border: 1px solid #334155; margin-bottom: 25px; box-shadow: 0 4px 10px rgba(0,0,0,0.2);">
    <div style="text-align: center; margin-bottom: 12px;">
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

page = st.sidebar.radio("القائمة الرئيسية", ["مركز إدارة المنتجات", "لوحة إدارة العروض الخاصة الحالية", "مركز إدارة العملاء والمجموعات"], label_visibility="collapsed")
st.sidebar.divider()

if st.sidebar.button("🔄 إعادة مزامنة البيانات", type="primary", use_container_width=True):
    perform_initial_sync_with_ui({"Authorization": f"Bearer {st.session_state['access_token']}"})
    st.rerun()

if st.sidebar.button("🚪 تسجيل الخروج", use_container_width=True, type="primary"):
    st.session_state["logged_in"] = False
    st.rerun()

if page == "مركز إدارة المنتجات": render_products_page()
elif page == "لوحة إدارة العروض الخاصة الحالية": render_offers_page()
elif page == "مركز إدارة العملاء والمجموعات": render_customers_page()
