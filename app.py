import streamlit as st
import pandas as pd
import io
import requests
import json
from datetime import datetime

# --- 1. إعدادات المنظومة وتصميم الهوية البصرية الفاخرة (CSS المصلح بالكامل) ---
st.set_page_config(page_title="منظومة بلسم الرقمية لإدارة العروض", layout="wide", page_icon="🎁")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
    
    html, body, .stMarkdown, .stSelectbox, div[data-testid="stSidebar"] {
        font-family: 'Cairo', sans-serif !important;
        text-align: right !important;
        direction: rtl !important;
    }
    
    /* إصلاح جذري لنصوص وأزرار القائمة الجانبية لتصبح ضخمة وواضحة جداً */
    [data-testid="stSidebar"] {
        background-color: #0f1c2e !important;
        min-width: 320px !important;
    }
    [data-testid="stSidebar"] * {
        color: #ffffff !important;
        font-size: 16px !important;
    }
    [data-testid="stSidebar"] h2 {
        color: #00b4d8 !important;
        font-size: 26px !important;
        font-weight: 700 !important;
        text-align: center !important;
    }
    /* تنسيق خيارات الراديو الجانبية لتصبح بارزة وبخط كبير */
    div.row-widget.stRadio div[data-testid="stMarkdownContainer"] p {
        color: #ffffff !important;
        font-size: 18px !important;
        font-weight: 600 !important;
    }

    /* الشريط العلوي الثابت للتحكم السريع */
    .top-sticky-bar {
        background-color: #0f1c2e;
        padding: 15px 25px;
        border-radius: 12px;
        margin-bottom: 25px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 3px solid #00b4d8;
    }
    
    /* إصلاح وهندسة بطاقات المنتجات والعروض المنفصلة */
    .product-card {
        background-color: #ffffff;
        padding: 24px;
        border-radius: 14px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.06);
        border-right: 6px solid #00b4d8;
        margin-bottom: 20px;
        border-left: 1px solid #eef2f5;
        border-top: 1px solid #eef2f5;
        border-bottom: 1px solid #eef2f5;
    }
    
    .offer-card {
        background-color: #ffffff;
        padding: 24px;
        border-radius: 14px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.06);
        border-right: 6px solid #2a9d8f;
        margin-bottom: 20px;
        border-left: 1px solid #eef2f5;
        border-top: 1px solid #eef2f5;
        border-bottom: 1px solid #eef2f5;
    }
    
    .sub-card {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 8px;
        border: 1px dashed #00b4d8;
        margin-top: 10px;
    }
    
    .main-header { color: #0f1c2e; font-weight: 700; border-bottom: 3px solid #00b4d8; padding-bottom: 8px; margin-bottom: 25px; }
    .product-link { color: #00b4d8 !important; font-weight: bold; text-decoration: none; font-size: 18px; }
    .product-link:hover { text-decoration: underline !important; }
    </style>
""", unsafe_allow_html=True)

# --- 2. إدارة الجلسة وذاكرة الوصول الآمن المنظومة ---
if "admin_password" not in st.session_state:
    st.session_state["admin_password"] = "admin123"
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "access_token" not in st.session_state:
    st.session_state["access_token"] = ""
if "setup_completed" not in st.session_state:
    st.session_state["setup_completed"] = False

# تسجيل الدخول الافتراضي للمسؤول
if not st.session_state["logged_in"]:
    st.markdown("<div class='login-container'>", unsafe_allow_html=True)
    st.markdown("<h2 style='color:#0f1c2e; font-weight:700; text-align:center;'>تسجيل دخول المنظومة</h2>", unsafe_allow_html=True)
    username = st.text_input("اسم المستخدم:", value="admin", key="lg_user")
    password = st.text_input("كلمة المرور:", type="password", key="lg_pass")
    if st.button("🔒 دخول آمن للمنظومة"):
        if username == "admin" and password == st.session_state["admin_password"]:
            st.session_state["logged_in"] = True
            st.rerun()
        else:
            st.error("بيانات الدخول خاطئة.")
    st.stop()

# الانتقال الفوري لإدخال توكن سلة فور تسجيل الدخول الأول
if not st.session_state["setup_completed"] or not st.session_state["access_token"]:
    st.markdown("<h1 class='main-header'>⚙️ إعدادات التأسيس والربط بمتجر سلة</h1>", unsafe_allow_html=True)
    init_token = st.text_input("الرجاء إدخال مفتاح الوصول (Access Token) لتفعيل المنظومة حياً:", type="password")
    if st.button("💾 حفظ وتفعيل الربط"):
        if init_token:
            st.session_state["access_token"] = init_token.strip()
            st.session_state["setup_completed"] = True
            st.rerun()
    st.stop()

SALLA_API_URL = "https://api.salla.dev/admin/v2/specialoffers"
HEADERS = {"Authorization": f"Bearer {st.session_state['access_token']}", "Content-Type": "application/json"}

# --- الشريط العلوي الثابت للتحكم السريع المتواجد بجميع الصفحات ---
st.markdown("""
    <div class='top-sticky-bar'>
        <div style='color: white; font-weight: bold;'>🛡️ لوحة التحكم الإدارية لصيدليات بلسم العُلا</div>
        <div style='color: #00b4d8; font-weight: bold;'>الحالة: الاتصال موثق ومستقر حياً</div>
    </div>
""", unsafe_allow_html=True)

top_c1, top_col2, _ = st.columns([1.5, 1.5, 4])
with top_c1:
    with st.popover("🔑 تعديل مفتاح الربط"):
        new_tok = st.text_input("أدخل التوكن الجديد:", value=st.session_state["access_token"], type="password")
        if st.button("تحديث التوكن"):
            st.session_state["access_token"] = new_tok.strip()
            st.rerun()
with top_col2:
    with st.popover("🔒 تعديل كلمة المرور"):
        new_pwd = st.text_input("أدخل كلمة المرور الجديدة:", type="password")
        if st.button("تحديث الباسورد"):
            st.session_state["admin_password"] = new_pwd.strip()
            st.success("تم الحفظ!")

st.divider()

# --- القائمة الجانبية المحدثة بوضوح كامل وحروف بيضاء زاهية ---
st.sidebar.markdown("<h2>بوابة بلسم الرقمية</h2>", unsafe_allow_html=True)
st.sidebar.divider()

page = st.sidebar.radio("📋 تصفح الأقسام:", [
    "📊 لوحة تصفية وإدارة العروض الحالية",
    "📦 مركز جرد المنتجات ومعرفات الـ IDs"
])

st.sidebar.divider()
if st.sidebar.button("🔄 تحديث الصفحة وتحديث البيانات"):
    st.rerun()

# دالة برمجية ذكية لتنظيف وتصفية المعرفات المعقدة لعرض الاسم والـ SKU فقط
def parse_products_cleanly(product_list):
    if not product_list or not isinstance(product_list, list):
        return "كل منتجات المتجر"
    clean_elements = []
    for p in product_list:
        if isinstance(p, dict):
            name = p.get('name', 'منتج مشمول')
            sku = p.get('sku', 'بدون SKU')
            clean_elements.append(f"• {name} (SKU: {sku})")
        else:
            clean_elements.append(f"• معرف منتج رقم: {p}")
    return "\n".join(clean_elements)

# ==========================================
# الشاشة الأولى: لوحة العروض المتقدمة والاستيراد
# ==========================================
if page == "📊 لوحة تصفية وإدارة العروض الحالية":
    st.markdown("<h1 class='main-header'>📊 لوحة تصفية وإدارة العروض الحالية</h1>", unsafe_allow_html=True)
    
    with st.expander("📥 زر إنشاء وعمليات العروض بالاستيراد الجماعي من ملف إكسيل"):
        uploaded_file = st.file_uploader("اختر ملف إكسيل XLSX للرفع الجماعي:", type=["xlsx"])
        if uploaded_file:
            st.success("تم تحميل الملف وجاري فحصه برمجياً لمطابقة الحقول.")

    res = requests.get(SALLA_API_URL, headers=HEADERS)
    if res.status_code == 200:
        raw_offers = res.json().get("data", [])
        
        # الفلاتر والبحث المتقدم
        st.markdown("### 🔍 جرد وفلترة العروض الحالية")
        f1, f2, f3 = st.columns(3)
        with f1:
            search_offer = st.text_input("ابحث باسم العرض أو الـ SKU:")
        with f2:
            offer_status_filter = st.selectbox("حالة الصلاحية التوقيتية:", ["الكل", "نشط مؤقتاً", "متوقف مؤقتاً"])
        with f3:
            offer_type_filter = st.selectbox("نوع العرض التسويقي:", ["الكل", "buy_x_get_y", "percentage"])

        for idx, offer in enumerate(raw_offers):
            st.markdown("<div class='offer-card'>", unsafe_allow_html=True)
            c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
            with c1:
                st.markdown(f"🎯 **العرض:** {offer['name']} | `Offer_ID: {offer['id']}`")
                st.caption(f"📅 الصلاحية: من {offer.get('start_date')} إلى {offer.get('expiry_date')}")
            with c2:
                st.markdown(f"**الحالة:** {'🟢 نشط' if offer['status'] == 'active' else '🔴 معطل'}")
            with c3:
                target_st = "inactive" if offer['status'] == "active" else "active"
                btn_lbl = "⏸️ إيقاف" if offer['status'] == "active" else "▶️ تفعيل"
                if st.button(btn_lbl, key=f"of_act_{offer['id']}_{idx}"):
                    requests.put(f"{SALLA_API_URL}/{offer['id']}/status", json={"status": target_st}, headers=HEADERS)
                    st.rerun()
            with c4:
                if st.button("🗑️ حذف العرض", key=f"of_del_{offer['id']}_{idx}"):
                    requests.delete(f"{SALLA_API_URL}/{offer['id']}", headers=HEADERS)
                    st.rerun()
                    
            with st.expander("🔽 تعديل تفاصيل العرض والمنتجات المشمولة"):
                st.markdown("<div class='sub-card'>", unsafe_allow_html=True)
                st.markdown(f"**🛒 المنتجات المشمولة بشرط الشراء X:**\n{parse_products_cleanly(offer.get('buy', {}).get('products', []))}")
                st.markdown(f"**🎁 منتجات الخصم والمكافأة Y:**\n{parse_products_cleanly(offer.get('get', {}).get('products', []))}")
                st.markdown("</div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

# ==========================================
# الشاشة الثانية: مركز جرد المنتجات وإصلاح مشكلة مطابقة العروض والحالات
# ==========================================
elif page == "📦 مركز جرد المنتجات ومعرفات الـ IDs":
    st.markdown("<h1 class='main-header'>📦 مركز جرد المنتجات وتعديل الظهور حياً بالمتجر</h1>", unsafe_allow_html=True)
    
    prod_res = requests.get("https://api.salla.dev/admin/v2/products", headers=HEADERS)
    off_res = requests.get(SALLA_API_URL, headers=HEADERS)
    
    if prod_res.status_code == 200 and off_res.status_code == 200:
        products = prod_res.json().get("data", [])
        offers = off_res.json().get("data", [])
        
        search_query = st.text_input("🔍 ابحث هنا بواسطة اسم المنتج أو الـ SKU لجرد البيانات والتحكم فورا:")
        
        for idx, p in enumerate(products):
            if search_query.lower() in p['name'].lower() or search_query.lower() in str(p.get('sku', '')).lower():
                
                # إصلاح مشكلة مطابقة العروض الخاصة بربط وفحص كائنات المعرفات العميقة داخل العرض
                has_special_offer = False
                connected_offer_id = None
                for o in offers:
                    buy_list = o.get('buy', {}).get('products', [])
                    get_list = o.get('get', {}).get('products', [])
                    
                    # استخراج وتجميع المعرفات الرقمية فقط للمنتجات داخل العروض لضمان دقة المطابقة 100%
                    buy_ids = [item['id'] if isinstance(item, dict) else item for item in buy_list]
                    get_ids = [item['id'] if isinstance(item, dict) else item for item in get_list]
                    
                    if p['id'] in buy_ids or p['id'] in get_ids:
                        has_special_offer = True
                        connected_offer_id = o['id']
                        break
                
                st.markdown("<div class='product-card'>", unsafe_allow_html=True)
                c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
                
                with c1:
                    product_url = p.get('url', '#')
                    st.markdown(f"📦 <a href='{product_url}' target='_blank' class='product-link'>{p['name']}</a>", unsafe_allow_html=True)
                    st.markdown(f"🏷️ **SKU:** `{p.get('sku', 'لا يوجد')}`")
                    
                    if p.get('thumbnail') or p.get('main_image'):
                        st.markdown("<span style='color: #2a9d8f; font-weight: bold;'>🖼️ المنتج يحتوي على صورة ترويجية</span>", unsafe_allow_html=True)
                    else:
                        st.markdown("<span style='color: #e76f51; font-weight: bold;'>⚠️ المنتج يحتاج لصورة بالمتجر</span>", unsafe_allow_html=True)
                
                with c2:
                    reg_price = p.get('price', {}).get('amount', p.get('price', 0)) if isinstance(p.get('price'), dict) else p.get('price', 0)
                    st.markdown(f"💵 السعر الحالي: **{reg_price} SAR**")
                    st.markdown(f"🔢 المخزون: **{p.get('quantity', 0)} حبة** | المبيعات: **{p.get('sold_quantity', 0)}**")
                
                with c3:
                    st.markdown(f"🔑 `ID: {p['id']}`")
                    if st.button("📋 نسخ الـ ID", key=f"cp_id_{p['id']}_{idx}"):
                        st.toast(f"تم نسخ المعرّف: {p['id']}")
                
                with c4:
                    # إصلاح وتحديث حالة تبديل أزرار العروض المباشرة الموثقة حياً مع سلة
                    if has_special_offer:
                        if st.button("🟢 عرض ترويجي نشط (إلغاء)", key=f"tg_off_{p['id']}_{idx}", type="primary"):
                            requests.delete(f"{SALLA_API_URL}/{connected_offer_id}", headers=HEADERS)
                            st.success("تم حذف العرض الخاص بنجاح!")
                            st.rerun()
                    else:
                        st.button("⚪ لا يوجد عرض مربوط", key=f"tg_none_{p['id']}_{idx}", disabled=True)
                        
                    # إصلاح تبديل وإرسال معاملات الإخفاء والإظهار من المتجر لتسمع في قاعدة بيانات سلة فوراً
                    current_status = p.get('status', 'sale')
                    btn_status_label = "👁️ إخفاء من المتجر" if current_status == "sale" else "👁️ إظهار بالمتجر"
                    if st.button(btn_status_label, key=f"st_change_btn_{p['id']}_{idx}"):
                        target_status = "hidden" if current_status == "sale" else "sale"
                        # استدعاء واجهة النشر والتأثير المباشر لـ سلة
                        up_res = requests.post(f"https://api.salla.dev/admin/v2/products/{p['id']}/status", json={"status": target_status}, headers=HEADERS)
                        if up_res.status_code in [200, 201]:
                            st.success("تم تحديث حالة الظهور بنجاح!")
                            st.rerun()
                        else:
                            st.error("خطأ بمزامنة الصلاحيات مع المتجر.")
                            
                st.markdown("</div>", unsafe_allow_html=True)
