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
# 🔄 المزامنة الحية (مع شريط التقدم المطور)
# ==========================================
def perform_initial_sync_with_ui(headers):
    """المزامنة الحية التي تظهر شريط التقدم والعدادات أثناء الدخول"""
    placeholder = st.empty()
    with placeholder.container():
        st.markdown("""
        <div style='background: #0F1C2E; padding: 20px; border-radius: 12px; border: 1px solid #00EBCF; text-align: center;'>
            <h3 style='color: #00EBCF; margin-bottom: 15px;'>🔄 جاري تهيئة المنظومة وسحب بيانات متجرك...</h3>
        </div>
        """, unsafe_allow_html=True)
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # 1. سحب المنتجات
        status_text.info("📦 جاري الاتصال وسحب المنتجات...")
        products = []
        res = safe_api_request("GET", "https://api.salla.dev/admin/v2/products?per_page=100&page=1", headers)
        if res:
            tp = res.get("pagination", {}).get("totalPages", 1)
            products.extend(res.get("data", []))
            for page in range(2, tp + 1):
                status_text.info(f"📦 جاري سحب المنتجات: صفحة {page} من {tp} | (تم تحميل {len(products)} منتج)")
                p_res = safe_api_request("GET", f"https://api.salla.dev/admin/v2/products?per_page=100&page={page}", headers)
                if p_res and p_res.get("data"): products.extend(p_res["data"])
                progress_bar.progress(0.3 * (page / tp))
        st.session_state["all_products"] = products
        
        # 2. سحب العروض
        status_text.info("🎁 جاري سحب العروض الخاصة النشطة...")
        offers = []
        o_res = safe_api_request("GET", "https://api.salla.dev/admin/v2/specialoffers?per_page=100&page=1", headers)
        if o_res:
            tp = o_res.get("pagination", {}).get("totalPages", 1)
            offers.extend(o_res.get("data", []))
            for page in range(2, tp + 1):
                status_text.info(f"🎁 جاري سحب العروض: صفحة {page} من {tp}")
                op_res = safe_api_request("GET", f"https://api.salla.dev/admin/v2/specialoffers?per_page=100&page={page}", headers)
                if op_res and op_res.get("data"): offers.extend(op_res["data"])
                progress_bar.progress(0.3 + (0.3 * (page / tp)))
        st.session_state["all_offers"] = offers
        
        # 3. بناء خريطة العروض (الخوارزمية الذكية لظهور الشارات)
        status_text.info("🔗 جاري تحليل العروض وربطها بالمنتجات (لظهور الشارات)...")
        po_map = {"ALL_PRODUCTS": []}
        active_offers = [o for o in offers if o.get('status') == 'active']
        
        for idx, o in enumerate(active_offers):
            status_text.info(f"🔗 جاري تحليل العرض: {idx + 1} من {len(active_offers)}")
            oid = str(o.get("id"))
            full_o = safe_api_request("GET", f"https://api.salla.dev/admin/v2/specialoffers/{oid}", headers)
            if full_o and full_o.get("data"):
                data = full_o["data"]
                summary = {"id": oid, "name": data.get("name")}
                if data.get("applied_to") == "all":
                    po_map["ALL_PRODUCTS"].append(summary)
                else:
                    pids = set()
                    for p in data.get("buy", {}).get("products", []):
                        pid = str(p.get("id", p) if isinstance(p, dict) else p)
                        if pid.isdigit(): pids.add(pid)
                    for p in data.get("get", {}).get("products", []):
                        pid = str(p.get("id", p) if isinstance(p, dict) else p)
                        if pid.isdigit(): pids.add(pid)
                    for p in data.get("products", []): # للعروض المباشرة
                        pid = str(p.get("id", p) if isinstance(p, dict) else p)
                        if pid.isdigit(): pids.add(pid)
                    for pid in pids:
                        if pid not in po_map: po_map[pid] = []
                        po_map[pid].append(summary)
            progress_bar.progress(0.6 + (0.3 * ((idx+1) / len(active_offers))))
            
        st.session_state["product_offers_map"] = po_map
        
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
    
    /* تصميم واجهة الدخول الاحترافية */
    .login-container {
        background: rgba(15, 28, 46, 0.85);
        backdrop-filter: blur(10px);
        padding: 40px;
        border-radius: 15px;
        border: 1px solid rgba(0, 235, 207, 0.3);
        box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        max-width: 500px;
        margin: 50px auto;
    }
    .login-container h3 { color: #00EBCF; font-weight: bold; margin-bottom: 20px; }
    
    /* بقية التنسيقات */
    div.stButton > button[data-testid="baseButton-primary"] { background-color: #00EBCF !important; color: #0f1c2e !important; font-weight: bold !important; border-radius: 8px !important; }
    div.stButton > button[data-testid="baseButton-primary"]:hover { transform: scale(1.02) !important; box-shadow: 0 4px 15px rgba(0,235,207,0.4) !important; }
    
    [data-testid="stSidebar"] { background-color: #0f1c2e !important; padding: 20px 15px !important; }
    [data-testid="stSidebar"] * { color: #ffffff !important; }
    [data-testid="stSidebar"] div[role="radiogroup"] label {
        background: linear-gradient(135deg, #1E293B 0%, #0F1C2E 100%); padding: 14px 15px !important; margin-bottom: 16px !important;
        border-radius: 8px !important; transform: skewX(-12deg); border: 1px solid #334155; cursor: pointer; display: flex; align-items: center;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] label div[data-testid="stMarkdownContainer"] { transform: skewX(12deg); text-align: center; width: 100%; }
    [data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) { background: linear-gradient(135deg, #00EBCF 0%, #0284C7 100%) !important; }
    
    .blinking-dot { height: 12px; width: 12px; background-color: #10B981; border-radius: 50%; display: inline-block; box-shadow: 0 0 8px #10B981; animation: blinker 1.5s linear infinite; }
    @keyframes blinker { 50% { opacity: 0.3; box-shadow: 0 0 2px #10B981; } }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 🔐 تسجيل الدخول (في حاوية جذابة)
# ==========================================

if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if "admin_password" not in st.session_state: st.session_state["admin_password"] = "admin123"

if not st.session_state["logged_in"]:
    st.markdown("<div class='login-container'>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align:center;'>🏥 مدير المنظومة الذكي</h3>", unsafe_allow_html=True)
    
    token = st.text_input("🔑 مفتاح الربط (Access Token):", type="password")
    un = st.text_input("👤 اسم المستخدم:")
    pw = st.text_input("🔒 كلمة المرور:", type="password")
    
    if st.button("🚀 دخول آمن وبدء المزامنة", use_container_width=True, type="primary"):
        if un == "admin" and pw == st.session_state["admin_password"] and token.strip():
            headers = {"Authorization": f"Bearer {token.strip()}"}
            try:
                res = requests.get("https://api.salla.dev/admin/v2/store/info", headers=headers, timeout=10)
                if res.status_code < 400: st.session_state["store_name"] = res.json().get("data", {}).get("name", "متجر سلة")
            except: pass
            
            # 🚀 استدعاء المزامنة الحية التي تظهر العدادات
            perform_initial_sync_with_ui(headers)
            
            st.session_state["logged_in"] = True
            st.session_state["access_token"] = token.strip()
            st.rerun()
        else:
            st.error("❌ تأكد من صحة البيانات والتوكن المرفق!")
    st.markdown("</div>", unsafe_allow_html=True)
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
