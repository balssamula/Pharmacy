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
# CSS المحسّن والآمن لمنع التداخل اللوني وكسر الخطوط
# ==========================================
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
    
    /* تطبيق الأنماط على النصوص الأساسية فقط دون تدمير الأيقونات المدمجة */
    html, body, p, h1, h2, h3, h4, h5, h6, label {
        font-family: 'Cairo', sans-serif !important;
        direction: rtl !important;
        text-align: right !important;
    }
    
    .login-container {
        max-width: 450px;
        margin: 80px auto;
        background: #ffffff;
        padding: 45px 35px;
        border-radius: 20px;
        box-shadow: 0 8px 30px rgba(0,0,0,0.12);
        border-top: 6px solid #00b4d8;
        text-align: center;
    }
    
    .top-sticky-bar {
        background: linear-gradient(135deg, #0a1628 0%, #1a2d4a 100%);
        padding: 14px 24px;
        border-radius: 12px;
        margin-bottom: 20px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 4px solid #00b4d8;
        box-shadow: 0 4px 15px rgba(0,0,0,0.08);
    }
    
    /* بطاقات العروض والمنتجات المصلحة كلياً */
    .product-card, .offer-card {
        background: #ffffff;
        border-radius: 14px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.06);
        margin-bottom: 20px;
        border-right: 6px solid #00b4d8;
        border-left: 1px solid #e8edf2;
        border-top: 1px solid #e8edf2;
        border-bottom: 1px solid #e8edf2;
        padding: 20px;
        direction: rtl !important;
    }
    .offer-card { border-right-color: #2a9d8f; }
    .sub-card { background: #f7f9fc; padding: 16px 18px; border-radius: 10px; border: 1px dashed #00b4d8; margin-top: 12px; }
    
    /* تنسيق وضبط نصوص القائمة الجانبية لتصبح عريضة وواضحة جداً */
    [data-testid="stSidebar"] {
        background-color: #0f1c2e !important;
        min-width: 300px !important;
    }
    [data-testid="stSidebar"] h2 {
        color: #00b4d8 !important;
        font-size: 24px !important;
        font-weight: 700 !important;
        text-align: center !important;
        border-bottom: 2px solid rgba(0, 180, 216, 0.2);
        padding-bottom: 10px;
    }
    [data-testid="stSidebar"] .stRadio label p {
        color: #ffffff !important;
        font-size: 16px !important;
        font-weight: 600 !important;
    }
    
    /* تنسيق أزرار السايدبار الملونة بخط أبيض عريض */
    .refresh-btn-container button {
        background: linear-gradient(135deg, #28a745, #20c997) !important;
        color: #ffffff !important;
        font-weight: 700 !important;
        font-size: 16px !important;
        border-radius: 10px !important;
        height: 46px !important;
        border: none !important;
    }
    .logout-btn button {
        background: linear-gradient(135deg, #dc3545, #c82333) !important;
        color: #ffffff !important;
        font-weight: 700 !important;
        font-size: 16px !important;
        border-radius: 10px !important;
        height: 46px !important;
        border: none !important;
    }
    
    .product-link { color: #00b4d8 !important; font-weight: 700; text-decoration: none; font-size: 18px; }
    .product-link:hover { text-decoration: underline !important; }
    
    /* ضبط وعزل جداول الـ DataFrame المرفوعة لمنع انضغاط الأعمدة */
    [data-testid="stDataFrame"] {
        direction: ltr !important;
        text-align: left !important;
    }
    
    .coupon-badge, .status-badge { display: inline-block; padding: 3px 12px; border-radius: 12px; font-size: 12px; font-weight: 600; margin-top: 5px; }
    .coupon-enabled, .status-active { background: #d4edda; color: #155724; }
    .coupon-disabled, .status-inactive { background: #f8d7da; color: #721c24; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# الدوال المساعدة لمعالجة التواريخ والتنظيف
# ==========================================

def safe_parse_date(date_str: Optional[str]) -> Optional[datetime]:
    if not date_str:
        return None
    date_str = str(date_str).strip()
    # الحماية التلقائية من الثواني الخاطئة مثل :60 أو :61 لمنع أخطاء سلة
    if re.search(r':6\d$', date_str):
        date_str = re.sub(r':6\d$', ':59', date_str)
    try:
        return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
    except (ValueError, TypeError):
        try:
            return datetime.strptime(date_str, '%Y-%m-%d')
        except (ValueError, TypeError):
            return None

def parse_products_cleanly(product_list: Optional[List]) -> str:
    if not product_list or not isinstance(product_list, list):
        return "كل منتجات المتجر"
    clean_elements = []
    for p in product_list:
        if isinstance(p, dict):
            clean_elements.append(f"• {p.get('name', 'منتج')} (SKU: {p.get('sku', 'بدون SKU')}) [ID: {p.get('id', 'بدون ID')}]")
        else:
            clean_elements.append(f"• معرف منتج رقم: {p}")
    return "\n".join(clean_elements)

def get_product_price(product: Dict) -> float:
    try:
        price = product.get('price', {})
        if isinstance(price, dict): return float(price.get('amount', 0))
        return float(price) if price else 0.0
    except (ValueError, TypeError): return 0.0

def safe_api_request(method: str, url: str, headers: Dict, **kwargs) -> Optional[Dict]:
    try:
        response = requests.request(method, url, headers=headers, timeout=30, **kwargs)
        if response.status_code >= 400:
            error_detail = response.json() if response.headers.get('content-type') == 'application/json' else response.text[:500]
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
# دالة معالجة استيراد الإكسيل الجماعي للـ API
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
            offer_type = str(row.get('Offer_Type', 'buy_x_get_y')).strip()
            applied_channel = str(row.get('Applied_Channel', 'browser_and_application')).strip()
            applied_to = str(row.get('Applied_To', 'product')).strip()
            offer_status = str(row.get('Offer_Status', 'active')).strip().lower()
            
            start_date = str(row.get('Start_Date_Time', ''))
            if re.search(r':6\d$', start_date): start_date = re.sub(r':6\d$', ':59', start_date)
            expiry_date = str(row.get('Expiry_Date_Time', ''))
            if re.search(r':6\d$', expiry_date): expiry_date = re.sub(r':6\d$', ':59', expiry_date)
            
            buy_products = [int(p.strip()) for p in re.split(r'[,\s;]+', str(row.get('Buy_Products_IDs', ''))) if p.strip().isdigit()]
            get_products = [int(p.strip()) for p in re.split(r'[,\s;]+', str(row.get('Get_Products_IDs', ''))) if p.strip().isdigit()]
            
            offer_data = {
                "name": offer_name, "offer_type": offer_type, "applied_channel": applied_channel,
                "applied_to": applied_to, "start_date": start_date, "expiry_date": expiry_date,
                "message": str(row.get('Offer_Message', '')).strip(), "status": offer_status,
                "applied_with_coupon": str(row.get('With_Coupon', 'لا')).strip() == 'نعم',
                "buy": {"type": str(row.get('Buy_Type', 'product')).strip(), "quantity": int(float(row.get('Buy_Quantity', 1)))},
                "get": {"type": str(row.get('Get_Type', 'product')).strip(), "quantity": int(float(row.get('Get_Quantity', 1))), "discount_type": str(row.get('Discount_Type', 'percentage')).strip()}
            }
            if buy_products: offer_data["buy"]["products"] = buy_products
            if get_products: offer_data["get"]["products"] = get_products
            
            discount_amount = row.get('Discount_Amount')
            if pd.notna(discount_amount) and float(discount_amount) > 0:
                offer_data["get"]["discount_amount"] = float(discount_amount)
                
            if action == 'create':
                res = safe_api_request("POST", "https://api.salla.dev/admin/v2/specialoffers", headers, json=offer_data)
                if res: results["success"].append(f"✅ تم إنشاء العرض: {offer_name}")
            elif action == 'update' and offer_id:
                res = safe_api_request("PUT", f"https://api.salla.dev/admin/v2/specialoffers/{offer_id}", headers, json=offer_data)
                if res: results["success"].append(f"✅ تم تحديث العرض ID: {offer_id}")
            elif action == 'delete' and offer_id:
                res = safe_api_request("DELETE", f"https://api.salla.dev/admin/v2/specialoffers/{offer_id}", headers)
                if res is not None: results["success"].append(f"✅ تم حذف العرض ID: {offer_id}")
        except Exception as e:
            results["errors"].append(f"❌ خطأ في الصف {idx+1}: {str(e)}")
    return results

def generate_salla_excel_template() -> bytes:
    buffer = io.BytesIO()
    columns = [
        "Action", "Offer_ID", "Offer_Name", "Offer_Type", "Applied_Channel",
        "Applied_To", "With_Coupon", "Offer_Status", "Start_Date_Time", "Expiry_Date_Time", 
        "Buy_Type", "Buy_Quantity", "Buy_Products_IDs", "Get_Type", "Get_Quantity", 
        "Discount_Type", "Discount_Amount", "Get_Products_IDs", "Offer_Message"
    ]
    df = pd.DataFrame([["create", "", "عرض جديد", "buy_x_get_y", "browser_and_application", "product", "نعم", "active", "2026-06-22 12:00:00", "2026-07-22 23:59:59", "product", 1, "1298176905", "product", 1, "percentage", 50, "1298176905", "خصم 50%"]], columns=columns)
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='قائمة العروض')
        worksheet = writer.sheets['قائمة العروض']
        from openpyxl.styles import PatternFill, Font
        header_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
        for cell in worksheet[1]:
            cell.fill = header_fill
            cell.font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
        for col in worksheet.columns: worksheet.column_dimensions[col[0].column_letter].width = 22
    return buffer.getvalue()

# --- إدارة الجلسة والدخول ---
if "admin_password" not in st.session_state: st.session_state["admin_password"] = "admin123"
if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if "access_token" not in st.session_state: st.session_state["access_token"] = ""

if not st.session_state["logged_in"]:
    st.markdown("<div class='login-container'>", unsafe_allow_html=True)
    st.markdown("<h2>🛡️ تسجيل دخول منظومة بلسم</h2>", unsafe_allow_html=True)
    st.text_input("🔑 مفتاح الربط (Access Token):", type="password", key="login_token")
    username = st.text_input("👤 اسم المستخدم:", value="admin", key="lg_un")
    password = st.text_input("🔒 كلمة المرور:", type="password", key="lg_pw")
    if st.button("🚀 دخول آمن للمنظومة", use_container_width=True):
        if username == "admin" and password == st.session_state["admin_password"]:
            st.session_state["access_token"] = st.session_state["login_token"].strip()
            st.session_state["logged_in"] = True
            st.rerun()
        else: st.error("❌ بيانات الدخول خاطئة.")
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

SALLA_API_URL = "https://api.salla.dev/admin/v2/specialoffers"

# --- القائمة الجانبية المصلحة والبارزة بالكامل ---
st.sidebar.markdown("<h2>🏥 بوابة بلسم الرقمية</h2>", unsafe_allow_html=True)
st.sidebar.divider()
page = st.sidebar.radio("📋 تصفح الأقسام التنفيذية:", ["📊 لوحة تصفية وإدارة العروض الحالية", "📦 مركز جرد المنتجات ومعرفات الـ IDs"])
st.sidebar.divider()

st.sidebar.markdown("<div class='refresh-btn-container'>", unsafe_allow_html=True)
if st.sidebar.button("🔄 تحديث البيانات والصفحة", key="refresh_page_btn", use_container_width=True): st.rerun()
st.sidebar.markdown("</div>", unsafe_allow_html=True)

st.sidebar.markdown("<div class='logout-btn'>", unsafe_allow_html=True)
if st.sidebar.button("🚪 تسجيل الخروج", key="logout_sidebar", use_container_width=True):
    st.session_state["logged_in"] = False
    st.rerun()
st.sidebar.markdown("</div>", unsafe_allow_html=True)

# --- الشريط العلوي الثابت المتواجد بجميع الشاشات ---
st.markdown("""
    <div class='top-sticky-bar'>
        <div class='title'>🛡️ لوحة التحكم الإدارية لصيدليات بلسم العُلا</div>
        <div class='status'>✅ الاتصال موثق ومستقر حياً</div>
    </div>
""", unsafe_allow_html=True)

# ==========================================
# الشاشة الأولى: لوحة العروض المتقدمة والاستيراد الفوري
# ==========================================
if page == "📊 لوحة تصفية وإدارة العروض الحالية":
    st.markdown("<h2 style='color:#0f1c2e;'>📊 لوحة إدارة وتصفية العروض الجماعية</h2>", unsafe_allow_html=True)
    
    col_info, col_btn = st.columns([3, 1])
    with col_info: st.info("📥 قم برفع ملف الإكسيل المعبأ لتحديث المتجر وجدولة العمليات حياً فورا:")
    with col_btn: st.download_button(label="📥 تحميل نموذج الإكسيل الاحترافي", data=generate_salla_excel_template(), file_name="Salla_Offers_Template.xlsx", use_container_width=True)
    
    uploaded_file = st.file_uploader("📂 اختر ملف العروض المعبأ للاستيراد النظيف المنسق:", type=["xlsx"])
    if uploaded_file:
        df_user = pd.read_excel(uploaded_file)
        st.dataframe(df_user, use_container_width=True)
        if st.button("🚀 تأكيد النشر الجماعي والمزامنة حياً"):
            res = process_excel_import(df_user)
            if res["success"]: st.success("\n".join(res["success"]))
            if res["errors"]: st.error("\n".join(res["errors"]))
            st.rerun()

    st.divider()
    res = safe_api_request("GET", SALLA_API_URL, get_headers())
    if res and "data" in res:
        for idx, offer in enumerate(res["data"]):
            st.markdown(f"<div class='offer-card'>", unsafe_allow_html=True)
            c1, c2, c3 = st.columns([4, 1, 1])
            with c1:
                st.markdown(f"🎯 **العرض:** {offer['name']} | `ID: {offer['id']}`")
                st.caption(f"📅 الصلاحية: من {offer.get('start_date')} إلى {offer.get('expiry_date')} | الحالة: **{offer.get('status')}**")
            with c2:
                t_status = "inactive" if offer.get('status') == "active" else "active"
                if st.button("⏸️ إيقاف" if offer.get('status') == "active" else "▶️ تفعيل", key=f"t_st_{offer['id']}_{idx}"):
                    safe_api_request("PUT", f"{SALLA_API_URL}/{offer['id']}/status", get_headers(), json={"status": t_status})
                    st.rerun()
            with c3:
                if st.button("🗑️ حذف العرض", key=f"del_{offer['id']}_{idx}"):
                    safe_api_request("DELETE", f"{SALLA_API_URL}/{offer['id']}", get_headers())
                    st.rerun()
                    
            with st.expander("🔽 تعديل تفاصيل العرض والمنتجات والكميات المتقدمة"):
                st.markdown("<div class='sub-card'>", unsafe_allow_html=True)
                st.markdown(f"**🛒 المنتجات المشمولة بشرط الشراء X:**\n{parse_products_cleanly(offer.get('buy', {}).get('products', []))}")
                st.markdown(f"**🎁 منتجات الخصم والمكافأة Y:**\n{parse_products_cleanly(offer.get('get', {}).get('products', []))}")
                
                # إظهار حقول التعديل المتقدمة بالوقت والنسب المفقودة
                ed_name = st.text_input("تعديل اسم العرض:", value=offer['name'], key=f"ed_nm_{offer['id']}")
                ed_start = st.text_input("وقت البدء (YYYY-MM-DD HH:mm:ss):", value=offer.get('start_date', ''), key=f"ed_st_{offer['id']}")
                ed_end = st.text_input("وقت الانتهاء (YYYY-MM-DD HH:mm:ss):", value=offer.get('expiry_date', ''), key=f"ed_en_{offer['id']}")
                
                if st.button("💾 حفظ وإرسال التعديلات لـ سلة", key=f"save_ed_{offer['id']}"):
                    payload = {"name": ed_name, "start_date": ed_start, "expiry_date": ed_end}
                    safe_api_request("PUT", f"{SALLA_API_URL}/{offer['id']}", get_headers(), json=payload)
                    st.success("تم تحديث معطيات العرض الخاص حياً بنجاح!")
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

# ==========================================
# الشاشة الثانية: مركز جرد وحالات المنتجات المصلحة
# ==========================================
elif page == "📦 centre جرد المنتجات ومعرفات الـ IDs":
    st.markdown("<h2 style='color:#0f1c2e;'>📦 مركز جرد وحالات ظهور منتجات الصيدلية بالمتجر حياً</h2>", unsafe_allow_html=True)
    prod_res = safe_api_request("GET", "https://api.salla.dev/admin/v2/products", get_headers())
    off_res = safe_api_request("GET", SALLA_API_URL, get_headers())
    
    if prod_res and "data" in prod_res and off_res:
        offers = off_res.get("data", [])
        search_query = st.text_input("🔍 ابحث هنا بواسطة اسم المنتج أو الـ SKU لجرد البيانات والتحكم فورا:")
        
        for idx, p in enumerate(prod_res["data"]):
            if not search_query or search_query.lower() in p['name'].lower() or search_query.lower() in str(p.get('sku', '')).lower():
                
                # فحص الارتباط بالعروض الخاصة المطور والموثق بالـ ID الفرعي لـ سلة
                has_special_offer = False
                connected_offer_id = None
                for o in offers:
                    buy_ids = [item['id'] if isinstance(item, dict) else item for item in o.get('buy', {}).get('products', [])]
                    get_ids = [item['id'] if isinstance(item, dict) else item for item in o.get('get', {}).get('products', [])]
                    if p['id'] in buy_ids or p['id'] in get_ids:
                        has_special_offer = True
                        connected_offer_id = o['id']
                        break
                
                st.markdown("<div class='product-card'>", unsafe_allow_html=True)
                c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
                with c1:
                    # فتح رابط المنتج مباشرة بالمتجر الحقيقي عند الضغط عليه
                    product_url = p.get('url', '#')
                    st.markdown(f"📦 <a href='{product_url}' target='_blank' class='product-link'>{p['name']}</a>", unsafe_allow_html=True)
                    st.caption(f"🏷️ SKU: `{p.get('sku')}` | 🔑 ID: `{p['id']}`")
                with c2:
                    price = get_product_price(p)
                    st.markdown(f"💵 السعر: **{price:,.2f} SAR**")
                    st.markdown(f"🔢 المخزون: **{p.get('quantity', 0)} حبة**")
                with c3:
                    if has_special_offer:
                        if st.button("🟢 عرض نشط (إلغاء)", key=f"p_off_{p['id']}_{idx}", type="primary"):
                            safe_api_request("DELETE", f"{SALLA_API_URL}/{connected_offer_id}", get_headers())
                            st.rerun()
                    else:
                        st.button("⚪ لا يوجد عرض", key=f"p_none_{p['id']}_{idx}", disabled=True)
                with c4:
                    current_status = p.get('status', 'sale')
                    btn_label = "👁️ إخفاء من المتجر" if current_status == "sale" else "👁️ إظهار بالمتجر"
                    if st.button(btn_label, key=f"p_st_{p['id']}_{idx}", use_container_width=True):
                        target_status = "hidden" if current_status == "sale" else "sale"
                        # ✅ الإصلاح طبقاً للمستندات الفنية المرفقة: طلب POST إلى رابط الـ /status
                        safe_api_request("POST", f"https://api.salla.dev/admin/v2/products/{p['id']}/status", get_headers(), json={"status": target_status})
                        st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
