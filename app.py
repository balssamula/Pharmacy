import streamlit as st
import requests
import json
import os
from datetime import datetime, timedelta
from utils import get_headers, safe_api_request, get_branches_list

st.set_page_config(
    page_title="مدير المنظومة المركزي",
    layout="wide",
    page_icon="👑",
    initial_sidebar_state="expanded"
)

# ... (استيراد الصفحات الأخرى render_offers_page, etc.) ...

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
# الكود الأصلي للتطبيق يعمل هنا كما هو طبيعياً
# (st.sidebar.radio, استدعاء render_products_page وغيرها...)
