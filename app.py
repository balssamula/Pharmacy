import streamlit as st
import os
import base64
import requests
import time
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

def perform_initial_sync_with_ui(headers):
    """المزامنة الحية التي تظهر شريط التقدم والعدادات أثناء الدخول"""
    placeholder = st.empty()
    with placeholder.container():
        st.markdown("### 🔄 جاري تهيئة المنظومة وسحب بيانات متجرك...")
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
        
        # 3. بناء خريطة العروض (هنا يتم تجهيز الشارات لصفحة المنتجات!)
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
        
    placeholder.empty() # إخفاء شريط التقدم بعد الانتهاء

# ==========================================
# 🎨 CSS
# ==========================================
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
    html, body, .stApp, h1, h2, h3, h4, h5, h6, p, label, input, select, textarea, div[data-testid="stMarkdownContainer"] p, div.stSelectbox div { font-family: 'Cairo', sans-serif !important; }
    .stIcon, [data-testid="stIcon"], [class^="st-"] svg, svg, i, span[data-testid="stIconVisibility"], summary svg, button svg, [data-base-ui="icon"], [class*="Icon"], summary::after, .st-emotion-cache-p6w706, .st-emotion-cache-1n76uvr, [data-testid="stExpander"] svg { font-family: inherit !important; }
    div.stButton > button[data-testid="baseButton-primary"] { background-color: #0f5132 !important; color: #ffffff !important; border: 1px solid #0f5132 !important; box-shadow: 0 4px 6px rgba(0,0,0,0.08) !important; font-size: 14px !important; font-family: 'Cairo', sans-serif !important; }
    div.stButton > button[data-testid="baseButton-primary"]:hover { background-color: #146c43 !important; border-color: #146c43 !important; transform: scale(1.02) !important; }
    div[data-testid="stPopover"] button { background-color: #0f5132 !important; color: #ffffff !important; border-radius: 8px !important; }
    div.stButton > button[key*="t_dl_"] { background-color: #dc3545 !important; color: #ffffff !important; border: 1px solid #dc3545 !important; }
    [data-testid="stSidebar"] { background-color: #0f1c2e !important; padding: 20px 15px !important; }
    [data-testid="stSidebar"] * { color: #ffffff !important; }
    .stButton button { border-radius: 8px !important; font-weight: 600 !important; }
    [data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child { display: none !important; }
    [data-testid="stSidebar"] div[role="radiogroup"] label > div:nth-child(2) { width: 100% !important; margin: 0 !important; }
    [data-testid="stSidebar"] div[role="radiogroup"] label { background: linear-gradient(135deg, #1E293B 0%, #0F1C2E 100%); padding: 14px 15px !important; margin-bottom: 16px !important; border-radius: 8px !important; transform: skewX(-12deg); border: 1px solid #334155; position: relative; overflow: hidden; transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1); cursor: pointer; display: flex; align-items: center; box-shadow: 0 4px 8px rgba(0,0,0,0.2); width: 92% !important; margin-left: auto !important; margin-right: auto !important; }
    [data-testid="stSidebar"] div[role="radiogroup"] label div[data-testid="stMarkdownContainer"] { transform: skewX(12deg); text-align: center; width: 100%; position: relative; z-index: 2; }
    [data-testid="stSidebar"] div[role="radiogroup"] label div[data-testid="stMarkdownContainer"] p { color: #94A3B8 !important; font-weight: 700 !important; font-size: 15px !important; margin: 0 !important; transition: all 0.3s ease; }
    [data-testid="stSidebar"] div[role="radiogroup"] label::after { content: ''; position: absolute; left: -15px; top: 0; bottom: 0; width: 45px; background: repeating-linear-gradient(45deg, rgba(255,255,255,0.03), rgba(255,255,255,0.03) 4px, transparent 4px, transparent 8px); transform: skewX(12deg); border-right: 2px solid rgba(255,255,255,0.05); z-index: 1; transition: all 0.3s ease; }
    [data-testid="stSidebar"] div[role="radiogroup"] label:hover { background: linear-gradient(135deg, #2D3748 0%, #1E293B 100%); border-color: #00EBCF; transform: skewX(-12deg) scale(1.02); }
    [data-testid="stSidebar"] div[role="radiogroup"] label:hover div[data-testid="stMarkdownContainer"] p { color: #00EBCF !important; }
    [data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) { background: linear-gradient(135deg, #00EBCF 0%, #0284C7 100%) !important; border-color: #00EBCF !important; box-shadow: 0 0 20px rgba(0, 235, 207, 0.4) !important; transform: skewX(-12deg) scale(1.06) !important; }
    [data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) div[data-testid="stMarkdownContainer"] p { color: #FFFFFF !important; text-shadow: 1px 1px 3px rgba(0,0,0,0.4) !important; }
    [data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked)::after { border-right: 2px solid rgba(255,255,255,0.4); }
    .blinking-dot { height: 12px; width: 12px; background-color: #10B981; border-radius: 50%; display: inline-block; box-shadow: 0 0 8px #10B981; animation: blinker 1.5s linear infinite; }
    @keyframes blinker { 50% { opacity: 0.3; box-shadow: 0 0 2px #10B981; } }
    </style>
""", unsafe_allow_html=True)

if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if "access_token" not in st.session_state: st.session_state["access_token"] = ""
if "admin_password" not in st.session_state: st.session_state["admin_password"] = "admin123"
if "store_name" not in st.session_state: st.session_state["store_name"] = "متجر سلة"
if "login_time" not in st.session_state: st.session_state["login_time"] = ""

if not st.session_state["logged_in"]:
    _, col2, _ = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h3 style='text-align:center;'>🏥 تسجيل الدخول - مدير المنتجات والعروض الخاصة</h3>", unsafe_allow_html=True)
        st.divider()
        token = st.text_input("🔑 مفتاح الربط (Access Token):", type="password")
        un = st.text_input("👤 اسم المستخدم:")
        pw = st.text_input("🔒 كلمة المرور:", type="password")
        
        if st.button("🚀 دخول آمن للمنظومة وتحديث البيانات", use_container_width=True, type="primary"):
            if un == "admin" and pw == st.session_state["admin_password"] and token.strip():
                headers = {"Authorization": f"Bearer {token.strip()}"}
                try:
                    res = requests.get("https://api.salla.dev/admin/v2/store/info", headers=headers, timeout=10)
                    if res.status_code < 400: st.session_state["store_name"] = res.json().get("data", {}).get("name", "متجر سلة")
                except: pass
                
                ksa_time = datetime.now() + timedelta(hours=3)
                st.session_state["login_time"] = ksa_time.strftime("%Y-%m-%d %I:%M %p")
                st.session_state["logged_in"] = True
                st.session_state["access_token"] = token.strip()
                
                # 🚀 تشغيل المزامنة الحية مباشرة في الشاشة
                perform_initial_sync_with_ui(headers)
                
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
</div>
""", unsafe_allow_html=True)

st.markdown("---")

c_tok, c_pwd, _ = st.columns([2, 2, 4])
with c_tok:
    with st.popover("⚙️ إعدادات مفتاح الربط"):
        new_t = st.text_input("أدخل توكن الربط الجديد:", value=st.session_state["access_token"], type="password")
        if st.button("تحديث التوكن والربط", type="primary", use_container_width=True):
            st.session_state["access_token"] = new_t
            st.success("تم التحديث!")
            st.rerun()
with c_pwd:
    with st.popover("🔒 تعديل كلمة مرور النظام"):
        new_p = st.text_input("أدخل الباسورد الجديد:", type="password")
        if st.button("حفظ الباسورد الجديد", type="primary", use_container_width=True):
            st.session_state["admin_password"] = new_p
            st.success("تم الحفظ بنجاح!")

st.divider()

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
            آخر دخول: <b style="color: #CBD5E1; direction: ltr; display: inline-block;">{st.session_state.get('login_time', '')}</b>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

page = st.sidebar.radio("القائمة الرئيسية", ["مركز إدارة المنتجات", "لوحة إدارة العروض الخاصة الحالية", "مركز إدارة العملاء والمجموعات"], label_visibility="collapsed")
st.sidebar.divider()

col_refresh1, col_refresh2 = st.sidebar.columns(2)
with col_refresh1:
    if st.sidebar.button("🔄 مزامنة", type="primary", use_container_width=True):
        st.session_state["all_products_fetched"] = False
        perform_initial_sync_with_ui({"Authorization": f"Bearer {st.session_state['access_token']}"})
        st.rerun()

with col_refresh2:
    if st.sidebar.button("🚪 خروج", use_container_width=True, type="primary"):
        st.session_state["logged_in"] = False
        st.rerun()

if st.session_state.get("all_products_fetched", False):
    st.sidebar.success(f"✅ {len(st.session_state.get('all_products', []))} منتج")
    if st.session_state.get("product_offers_map"):
        st.sidebar.info(f"🔗 الروابط مفعلة ({len(st.session_state['product_offers_map'])})")
    
if page == "مركز إدارة المنتجات": render_products_page()
elif page == "لوحة إدارة العروض الخاصة الحالية": render_offers_page()
elif page == "مركز إدارة العملاء والمجموعات": render_customers_page()
