import streamlit as st
import requests
import json
import os
import base64
from datetime import datetime, timedelta
from utils import get_headers, safe_api_request, get_branches_list

st.set_page_config(page_title="مدير المنظومة المركزي", layout="wide", page_icon="👑", initial_sidebar_state="expanded")

from offers_page import render_offers_page
from products_page import render_products_page
from customers_page import render_customers_page

def perform_initial_sync_with_ui(headers):
    placeholder = st.empty()
    with placeholder.container():
        st.markdown("<div style='background: #0F1C2E; padding: 20px; border-radius: 12px; border: 1px solid #00EBCF; text-align: center; margin-bottom: 20px;'><h3 style='color: #00EBCF; margin: 0;'>🔄 جاري تهيئة المنظومة وسحب بيانات متجرك...</h3></div>", unsafe_allow_html=True)
        progress_bar = st.progress(0)
        status_text = st.empty()
        
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
                progress_bar.progress(0.4 * (page / tp))
        st.session_state["all_products"] = products
        
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
                progress_bar.progress(0.4 + (0.4 * (page / tp)))
        st.session_state["all_offers"] = offers
        
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
        
        status_text.info("🏢 جاري جلب الفروع والمستودعات...")
        st.session_state["branches"] = get_branches_list()
        progress_bar.progress(1.0)
        st.session_state["all_products_fetched"] = True
        st.session_state["last_sync_time"] = datetime.now().strftime("%Y-%m-%d %I:%M %p")
    placeholder.empty()

if "is_admin_logged_in" not in st.session_state: st.session_state["is_admin_logged_in"] = False
if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if "admin_username" not in st.session_state: st.session_state["admin_username"] = "admin"
if "admin_password" not in st.session_state: st.session_state["admin_password"] = "admin123"
if "access_token" not in st.session_state: st.session_state["access_token"] = ""
if "store_name" not in st.session_state: st.session_state["store_name"] = "متجر سلة"

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
                    st.session_state["is_admin_logged_in"] = True; st.rerun()
                else: st.error("❌ بيانات الدخول غير صحيحة!")
    st.stop()

if st.session_state["is_admin_logged_in"] and not st.session_state["logged_in"]:
    st.markdown("""
    <div style="background: linear-gradient(135deg, #1E293B 0%, #0F1C2E 100%); padding: 25px; border-radius: 12px; color: white; text-align: center; margin-bottom: 30px; border-bottom: 4px solid #00EBCF;">
        <h1 style="color: white; margin: 0;">🌐 لوحة التحكم المركزية للمتاجر المربوطة</h1>
        <p style="color: #94A3B8; margin-top: 5px;">اختر المتجر الذي ترغب في إدارته من القائمة أدناه</p>
    </div>
    """, unsafe_allow_html=True)
    
    stores_db_path = "stores.json"
    connected_stores = []
    if os.path.exists(stores_db_path):
        with open(stores_db_path, "r", encoding="utf-8") as f:
            try: connected_stores = json.load(f)
            except: pass
    else: st.warning("⚠️ ملف قاعدة بيانات المتاجر (stores.json) غير موجود حتى الآن. سيتم إنشاؤه عند تسجيل أول متجر.")

    if connected_stores:
        cols = st.columns(3)
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
                    if st.button(f"🔑 إدارة هذا المتجر", key=f"login_store_{store.get('merchant_id')}", use_container_width=True, type="primary"):
                        token = store.get("access_token")
                        headers = {"Authorization": f"Bearer {token}"}
                        perform_initial_sync_with_ui(headers)
                        st.session_state["store_name"] = store.get('store_name')
                        st.session_state["logged_in"] = True
                        st.session_state["access_token"] = token
                        st.rerun()
    else:
        st.info("لم يقم أي تاجر بتثبيت التطبيق حتى الآن.")

    st.divider()
    if st.button("🚪 تسجيل الخروج من حساب المدير", type="secondary"):
        st.session_state["is_admin_logged_in"] = False; st.rerun()
    st.stop()

# --- بعد اختيار المتجر ---
st.markdown("""
<div style="background: linear-gradient(135deg, #1E293B 0%, #3B82F6 100%); padding: 25px; border-radius: 12px; color: white; text-align: center; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
    <h1 style="color: white; margin: 0; font-size: 2.2rem;">🎁 منظومة إدارة المنتجات والعروض الخاصة</h1>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown(f"""
<div style="background: linear-gradient(135deg, #0F1C2E, #1a365d); padding: 20px 15px; border-radius: 12px; border: 1px solid #334155; margin-bottom: 25px;">
    <div style="text-align: center; margin-bottom: 12px;">
        <div style="font-size: 32px; margin-bottom: 5px;">🏪</div>
        <h3 style="color: #FFFFFF; margin: 0; font-size: 18px;">{st.session_state.get('store_name', 'متجرك')}</h3>
    </div>
</div>
""", unsafe_allow_html=True)

page = st.sidebar.radio("القائمة الرئيسية", ["مركز إدارة المنتجات", "لوحة إدارة العروض الخاصة الحالية", "مركز إدارة العملاء والمجموعات"], label_visibility="collapsed")
st.sidebar.divider()

if st.sidebar.button("🔄 إعادة مزامنة البيانات", type="primary", use_container_width=True):
    perform_initial_sync_with_ui({"Authorization": f"Bearer {st.session_state['access_token']}"}); st.rerun()

if st.sidebar.button("🚪 العودة للوحة الإدارة (الخروج من المتجر)", use_container_width=True):
    st.session_state["logged_in"] = False; st.rerun()

if page == "مركز إدارة المنتجات": render_products_page()
elif page == "لوحة إدارة العروض الخاصة الحالية": render_offers_page()
elif page == "مركز إدارة العملاء والمجموعات": render_customers_page()
