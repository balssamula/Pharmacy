import streamlit as st
import pandas as pd
import io
import requests
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
import logging
import traceback
import re

# --- إعدادات التسجيل ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- إعدادات الصفحة ---
st.set_page_config(
    page_title="منظومة بلسم الرقمية لإدارة العروض",
    layout="wide",
    page_icon="🎁",
    initial_sidebar_state="expanded"
)

# ==========================================
# CSS الاحترافي المحسّن بالكامل
# ==========================================
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&display=swap');
    
    :root {
        --primary-color: #00b4d8;
        --secondary-color: #0f1c2e;
        --accent-color: #2a9d8f;
        --danger-color: #e63946;
        --warning-color: #ffb703;
        --text-dark: #2d3436;
        --text-light: #636e72;
        --bg-light: #f8f9fa;
        --white: #ffffff;
        --shadow: 0 4px 20px rgba(0,0,0,0.08);
    }

    * {
        font-family: 'Cairo', sans-serif !important;
        direction: rtl !important;
        text-align: right !important;
        box-sizing: border-box !important;
    }
    
    /* تحسين شكل الحاويات الرئيسية */
    .stApp {
        background-color: var(--bg-light);
    }

    .login-container {
        max-width: 450px;
        margin: 80px auto;
        background: var(--white);
        padding: 45px 35px;
        border-radius: 24px;
        box-shadow: var(--shadow);
        border-top: 8px solid var(--primary-color);
        text-align: center;
        animation: fadeIn 0.6s ease-out;
    }
    
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(-20px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    /* شريط العنوان العلوي */
    .top-sticky-bar {
        background: linear-gradient(135deg, #0f1c2e 0%, #1a2d4a 100%);
        padding: 16px 28px;
        border-radius: 16px;
        margin-bottom: 25px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 4px solid var(--primary-color);
        box-shadow: 0 6px 20px rgba(0,0,0,0.1);
        flex-wrap: wrap;
        gap: 15px;
    }
    
    .top-sticky-bar .title {
        color: var(--white);
        font-weight: 800;
        font-size: 18px;
        display: flex;
        align-items: center;
        gap: 12px;
    }
    
    /* بطاقات المنتجات والعروض المحسنة */
    .product-card, .offer-card {
        background: var(--white);
        border-radius: 18px;
        box-shadow: var(--shadow);
        margin-bottom: 24px;
        border: 1px solid #edf2f7;
        overflow: hidden;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        position: relative;
    }
    
    .product-card:hover, .offer-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 12px 30px rgba(0,0,0,0.12);
    }
    
    .product-card-header {
        background: linear-gradient(135deg, #0f1c2e 0%, #1e3a5f 100%);
        padding: 15px 25px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 3px solid var(--primary-color);
    }
    
    .product-card-header .product-name {
        color: var(--white);
        font-size: 18px;
        font-weight: 700;
    }
    
    .product-card-header .product-promotion {
        color: #ffd700;
        font-size: 13px;
        font-weight: 600;
        background: rgba(255, 215, 0, 0.15);
        padding: 4px 14px;
        border-radius: 30px;
        border: 1px solid rgba(255, 215, 0, 0.3);
    }
    
    .product-card-body, .offer-card-body {
        padding: 20px 25px;
    }

    /* حل مشكلة تداخل الأزرار والنصوص */
    .stButton > button {
        width: 100% !important;
        font-weight: 700 !important;
        border-radius: 12px !important;
        height: 44px !important;
        border: none !important;
        transition: all 0.3s ease !important;
        margin-bottom: 8px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        gap: 8px !important;
    }

    /* تحسين توزيع الأعمدة لمنع التداخل */
    .column-container {
        display: flex;
        flex-direction: column;
        gap: 12px;
        padding: 10px;
    }

    /* شارات الحالة */
    .badge {
        display: inline-flex;
        align-items: center;
        padding: 4px 12px;
        border-radius: 30px;
        font-size: 12px;
        font-weight: 700;
        margin: 4px;
    }
    
    .badge-active { background: #dcfce7; color: #166534; }
    .badge-inactive { background: #fee2e2; color: #991b1b; }
    .badge-info { background: #e0f2fe; color: #075985; }
    
    /* تحسين السايدبار */
    [data-testid="stSidebar"] {
        background-color: var(--secondary-color) !important;
        padding: 30px 15px !important;
    }
    
    [data-testid="stSidebar"] * {
        color: var(--white) !important;
    }
    
    [data-testid="stSidebar"] h2 {
        color: var(--primary-color) !important;
        font-size: 24px !important;
        border-bottom: 2px solid rgba(0, 180, 216, 0.2);
        padding-bottom: 15px;
        margin-bottom: 20px;
    }

    /* تنسيق المدخلات */
    .stTextInput input, .stSelectbox select, .stNumberInput input {
        border-radius: 12px !important;
        border: 2px solid #e2e8f0 !important;
        padding: 10px 15px !important;
    }

    .stTextInput input:focus {
        border-color: var(--primary-color) !important;
        box-shadow: 0 0 0 3px rgba(0, 180, 216, 0.1) !important;
    }

    /* التذييل */
    .footer {
        text-align: center;
        padding: 30px;
        color: var(--text-light);
        border-top: 1px solid #edf2f7;
        margin-top: 50px;
        background: var(--white);
    }
    
    /* منع ظهور الأكواد فوق الأزرار */
    code {
        background: #f1f5f9 !important;
        color: #475569 !important;
        padding: 2px 6px !important;
        border-radius: 6px !important;
        font-family: monospace !important;
        font-size: 0.9em !important;
    }
    
    .offer-details-box {
        background: #f8fafc;
        border-radius: 12px;
        padding: 15px;
        border-right: 5px solid var(--primary-color);
        margin: 10px 0;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# دوال مساعدة
# ==========================================

def safe_parse_date(date_str: Optional[str]) -> Optional[datetime]:
    if not date_str:
        return None
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            return datetime.strptime(date_str, fmt)
        except (ValueError, TypeError):
            continue
    return None

def parse_products_cleanly(product_list: Optional[List]) -> str:
    if not product_list or not isinstance(product_list, list):
        return "كل منتجات المتجر"
    
    clean_elements = []
    for p in product_list:
        try:
            if isinstance(p, dict):
                name = p.get('name', 'منتج مشمول')
                sku = p.get('sku', 'بدون SKU')
                product_id = p.get('id', 'بدون ID')
                clean_elements.append(f"• {name} (SKU: {sku}) [ID: {product_id}]")
            else:
                clean_elements.append(f"• معرف منتج رقم: {p}")
        except Exception:
            clean_elements.append("• منتج غير معرف")
    
    return "\n".join(clean_elements) if clean_elements else "لا توجد منتجات"

def get_product_price(product: Dict) -> float:
    try:
        price = product.get('price', {})
        if isinstance(price, dict):
            return float(price.get('amount', 0))
        return float(price) if price else 0.0
    except (ValueError, TypeError):
        return 0.0

def safe_api_request(method: str, url: str, headers: Dict, **kwargs) -> Optional[Dict]:
    try:
        response = requests.request(method, url, headers=headers, timeout=30, **kwargs)
        if response.status_code >= 400:
            try:
                error_detail = json.dumps(response.json(), ensure_ascii=False)
            except:
                error_detail = response.text[:500]
            st.error(f"⚠️ خطأ {response.status_code}: {error_detail}")
            return None
        return response.json()
    except Exception as e:
        st.error(f"⚠️ خطأ في الاتصال: {str(e)}")
        return None

def get_headers():
    return {
        "Authorization": f"Bearer {st.session_state.get('access_token', '')}",
        "Content-Type": "application/json"
    }

# ==========================================
# معالجة ملف الإكسيل
# ==========================================

def process_excel_import(df: pd.DataFrame) -> Dict:
    results = {"success": [], "errors": []}
    headers = get_headers()
    
    for idx, row in df.iterrows():
        try:
            action = str(row.get('Action', 'create')).strip().lower()
            offer_id = row.get('Offer_ID')
            if offer_id and isinstance(offer_id, float) and offer_id.is_integer():
                offer_id = int(offer_id)
            
            offer_name = str(row.get('Offer_Name', 'عرض جديد')).strip()
            offer_status = str(row.get('Offer_Status', 'active')).strip().lower()
            
            # بناء البيانات (مبسط للمثال)
            offer_data = {
                "name": offer_name,
                "status": offer_status,
                "offer_type": str(row.get('Offer_Type', 'buy_x_get_y')).strip(),
                "applied_to": str(row.get('Applied_To', 'product')).strip(),
                "applied_with_coupon": str(row.get('With_Coupon', 'لا')).strip() == 'نعم'
            }
            
            # تنفيذ الطلبات بناءً على الأكشن
            if action == 'create':
                res = safe_api_request("POST", "https://api.salla.dev/admin/v2/specialoffers", headers, json=offer_data)
                if res: results["success"].append(f"✅ تم إنشاء: {offer_name}")
            elif action == 'update' and offer_id:
                res = safe_api_request("PUT", f"https://api.salla.dev/admin/v2/specialoffers/{offer_id}", headers, json=offer_data)
                if res: results["success"].append(f"✅ تم تحديث ID: {offer_id}")
            elif action == 'delete' and offer_id:
                res = safe_api_request("DELETE", f"https://api.salla.dev/admin/v2/specialoffers/{offer_id}", headers)
                if res: results["success"].append(f"✅ تم حذف ID: {offer_id}")
                
        except Exception as e:
            results["errors"].append(f"❌ خطأ في الصف {idx+1}: {str(e)}")
    return results

# ==========================================
# الواجهة الرئيسية
# ==========================================

# التحقق من الدخول (محاكاة)
if 'access_token' not in st.session_state:
    st.session_state['access_token'] = ""

if not st.session_state['access_token']:
    with st.container():
        st.markdown('<div class="login-container">', unsafe_allow_html=True)
        st.image("https://salla.sa/assets/images/logo-light.png", width=120)
        st.markdown("### تسجيل الدخول للمنظومة")
        token = st.text_input("أدخل توكن الوصول (Access Token):", type="password")
        if st.button("🚀 دخول للمنظومة"):
            if token:
                st.session_state['access_token'] = token
                st.success("تم تسجيل الدخول بنجاح!")
                st.rerun()
            else:
                st.warning("يرجى إدخال التوكن")
        st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# شريط جانبي
with st.sidebar:
    st.markdown("## ⚙️ التحكم")
    page = st.radio("انتقل إلى:", ["🎯 إدارة العروض الترويجية", "📦 مركز جرد المنتجات ومعرفات الـ IDs"])
    st.divider()
    if st.button("🔄 تحديث البيانات", use_container_width=True):
        st.rerun()
    if st.button("🚪 تسجيل الخروج", use_container_width=True, type="primary"):
        st.session_state['access_token'] = ""
        st.rerun()

SALLA_API_URL = "https://api.salla.dev/admin/v2/specialoffers"

# الصفحة الأولى: إدارة العروض
if page == "🎯 إدارة العروض الترويجية":
    st.markdown("""
        <div class="top-sticky-bar">
            <div class="title">🎯 إدارة العروض الترويجية الذكية</div>
            <div style="color: #00b4d8; font-weight: 600;">نظام بلسم المتكامل</div>
        </div>
    """, unsafe_allow_html=True)

    # قسم الاستيراد
    with st.expander("📤 استيراد العروض عبر Excel", expanded=False):
        uploaded_file = st.file_uploader("اختر ملف Excel", type=["xlsx"])
        if uploaded_file:
            df = pd.read_excel(uploaded_file)
            st.dataframe(df, use_container_width=True)
            if st.button("🚀 تنفيذ العمليات الجماعية"):
                with st.spinner("جاري العمل..."):
                    res = process_excel_import(df)
                    for s in res["success"]: st.success(s)
                    for e in res["errors"]: st.error(e)

    st.divider()

    # عرض العروض
    with st.spinner("جاري جلب العروض..."):
        res = safe_api_request("GET", SALLA_API_URL, get_headers())
    
    if res and res.get("data"):
        offers = res["data"]
        
        # فلترة بسيطة
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            search = st.text_input("🔎 ابحث باسم العرض:", placeholder="اكتب هنا...")
        with col_s2:
            st.markdown(f"<div style='margin-top: 30px;'><b>إجمالي العروض: {len(offers)}</b></div>", unsafe_allow_html=True)

        for idx, offer in enumerate(offers):
            if search and search.lower() not in offer.get('name', '').lower():
                continue
                
            offer_id = offer.get('id')
            status = offer.get('status', 'inactive')
            status_badge = f'<span class="badge badge-active">مفعل</span>' if status == 'active' else f'<span class="badge badge-inactive">غير مفعل</span>'
            
            st.markdown(f"""
                <div class="offer-card">
                    <div class="offer-card-body">
                        <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                            <div>
                                <h4 style="margin: 0; color: #0f1c2e;">🎯 {offer.get('name')}</h4>
                                <p style="color: #636e72; font-size: 14px; margin: 5px 0;">ID: <code>{offer_id}</code> | {status_badge}</p>
                            </div>
                            <div style="text-align: left;">
                                <span class="badge badge-info">🏷️ {offer.get('offer_type')}</span>
                            </div>
                        </div>
            """, unsafe_allow_html=True)
            
            # أزرار التحكم في العرض - توزيع احترافي لمنع التداخل
            c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
            with c1:
                st.markdown(f"📅 **الفترة:** {offer.get('start_date')} → {offer.get('expiry_date')}")
            with c2:
                label = "⏸️ إيقاف" if status == 'active' else "▶️ تفعيل"
                if st.button(label, key=f"tgl_{offer_id}_{idx}"):
                    new_status = 'inactive' if status == 'active' else 'active'
                    safe_api_request("PUT", f"{SALLA_API_URL}/{offer_id}/status", get_headers(), json={"status": new_status})
                    st.rerun()
            with c3:
                if st.button("🗑️ حذف", key=f"del_{offer_id}_{idx}", type="primary"):
                    safe_api_request("DELETE", f"{SALLA_API_URL}/{offer_id}", get_headers())
                    st.rerun()
            with c4:
                show_details = st.toggle("تفاصيل", key=f"tgl_det_{offer_id}")

            if show_details:
                st.markdown('<div class="offer-details-box">', unsafe_allow_html=True)
                det_col1, det_col2 = st.columns(2)
                with det_col1:
                    st.write("**🛒 المشتريات:**")
                    st.code(parse_products_cleanly(offer.get('buy', {}).get('products', [])))
                with det_col2:
                    st.write("**🎁 الهدايا:**")
                    st.code(parse_products_cleanly(offer.get('get', {}).get('products', [])))
                st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown("</div></div>", unsafe_allow_html=True)

# الصفحة الثانية: جرد المنتجات
elif page == "📦 مركز جرد المنتجات ومعرفات الـ IDs":
    st.markdown("""
        <div class="top-sticky-bar">
            <div class="title">📦 مركز جرد المنتجات</div>
            <div style="color: #00b4d8; font-weight: 600;">إدارة المخزون والهوية</div>
        </div>
    """, unsafe_allow_html=True)

    with st.spinner("جاري تحميل المنتجات..."):
        p_res = safe_api_request("GET", "https://api.salla.dev/admin/v2/products", get_headers())
    
    if p_res and p_res.get("data"):
        products = p_res["data"]
        search_p = st.text_input("🔍 ابحث عن منتج (اسم أو SKU أو ID):")
        
        for p in products:
            if search_p and not any(search_p.lower() in str(p.get(k, '')).lower() for k in ['name', 'sku', 'id']):
                continue
                
            p_id = p.get('id')
            p_status = p.get('status', 'sale')
            status_text = "🟢 معروض" if p_status == "sale" else "🔴 مخفي"
            
            st.markdown(f"""
                <div class="product-card">
                    <div class="product-card-header">
                        <span class="product-name">📦 {p.get('name')}</span>
                        <span class="product-promotion">SKU: {p.get('sku')}</span>
                    </div>
                    <div class="product-card-body">
            """, unsafe_allow_html=True)
            
            pc1, pc2, pc3 = st.columns([2, 1.5, 1.5])
            with pc1:
                st.markdown(f"**💰 السعر:** {get_product_price(p)} SAR")
                st.markdown(f"**📦 المخزون:** {p.get('quantity', 0)} | **📈 المبيعات:** {p.get('sold_quantity', 0)}")
                st.markdown(f"**👁️ الحالة:** {status_text}")
            with pc2:
                if st.button("📋 نسخ ID المنتج", key=f"cp_{p_id}"):
                    st.toast(f"تم النسخ: {p_id}")
                if st.button("👁️ تغيير الظهور", key=f"vis_{p_id}"):
                    new_s = "hidden" if p_status == "sale" else "sale"
                    safe_api_request("PUT", f"https://api.salla.dev/admin/v2/products/{p_id}", get_headers(), json={"status": new_s})
                    st.rerun()
            with pc3:
                product_url = p.get('url', '#')
                st.markdown(f'<a href="{product_url}" target="_blank"><button style="width:100%; height:44px; border-radius:12px; background:#0f1c2e; color:white; border:none; cursor:pointer; font-weight:bold;">🔗 رابط المتجر</button></a>', unsafe_allow_html=True)

            st.markdown("</div></div>", unsafe_allow_html=True)

# التذييل
st.markdown("""
    <div class="footer">
        <p>© 2026 منظومة بلسم الرقمية | تم التطوير باحترافية لتواكب تطلعاتكم</p>
        <p style="font-size: 12px; color: #a0aec0;">الإصدار الاحترافي 2.0</p>
    </div>
""", unsafe_allow_html=True)
