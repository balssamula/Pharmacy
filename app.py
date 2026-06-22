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
# CSS الاحترافي المصلح بالكامل لمنع التداخل والخطوط البيضاء
# ==========================================
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
    
    /* تطبيق الخط والاتجاه على النصوص والفقرات دون تدمير عناصر النظام المدمجة */
    html, body, p, h1, h2, h3, h4, h5, h6, span, label {
        font-family: 'Cairo', sans-serif !important;
        direction: rtl !important;
        text-align: right !important;
    }
    
    /* إصلاح حاوية الدخول */
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
    
    /* إصلاح شريط الحالة العلوي ومنع تداخل أزرار البوب اوفر */
    .top-sticky-bar {
        background: linear-gradient(135deg, #0a1628 0%, #1a2d4a 100%);
        padding: 16px 24px;
        border-radius: 12px;
        margin-bottom: 25px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 4px solid #00b4d8;
        box-shadow: 0 4px 15px rgba(0,0,0,0.08);
    }
    
    .top-sticky-bar .title {
        color: #ffffff !important;
        font-weight: 700;
        font-size: 18px;
    }
    
    .top-sticky-bar .status {
        color: #00b4d8 !important;
        font-weight: 600;
        font-size: 14px;
        background: rgba(0, 180, 216, 0.12);
        padding: 6px 16px;
        border-radius: 20px;
        border: 1px solid rgba(0, 180, 216, 0.3);
    }
    
    /* تخصيص مظهر الأزرار الجانبية لمنع الخلفيات البيضاء واختفاء الخط */
    .refresh-btn-container button {
        background: linear-gradient(135deg, #28a745, #20c997) !important;
        color: #ffffff !important;
        font-weight: 700 !important;
        font-size: 15px !important;
        border-radius: 8px !important;
        height: 45px !important;
        border: none !important;
        box-shadow: 0 4px 12px rgba(40, 167, 69, 0.3) !important;
    }
    
    .logout-btn container, .logout-btn button {
        background: linear-gradient(135deg, #dc3545, #c82333) !important;
        color: #ffffff !important;
        font-weight: 700 !important;
        font-size: 15px !important;
        border-radius: 8px !important;
        height: 45px !important;
        border: none !important;
        box-shadow: 0 4px 12px rgba(220, 53, 69, 0.3) !important;
    }
    
    /* تعديل عناصر القائمة الجانبية لتصبح النصوص زاهية وواضحة */
    [data-testid="stSidebar"] {
        background-color: #0f1c2e !important;
    }
    
    [data-testid="stSidebar"] h2 {
        color: #00b4d8 !important;
        font-size: 22px !important;
        font-weight: 700 !important;
        text-align: center !important;
        border-bottom: 2px solid rgba(0, 180, 216, 0.2);
        padding-bottom: 10px;
    }
    
    [data-testid="stSidebar"] .stRadio label p {
        color: #ffffff !important;
        font-size: 15px !important;
        font-weight: 600 !important;
    }
    
    /* إجبار الجداول التابعة لـ streamlit (ملف الإكسيل) على الانضباط الكامل دون قلب الحروف */
    [data-testid="stDataFrame"] {
        direction: ltr !important; /* الجداول البرمجية يجب أن تبقى يسار لليمين لمنع تشوه أسماء الأعمدة */
        text-align: left !important;
    }
    
    /* تصميم البطاقات والعروض المستقرة */
    .product-card, .offer-card {
        background: #ffffff;
        border-radius: 12px;
        box-shadow: 0 2px 12px rgba(0,0,0,0.06);
        margin-bottom: 20px;
        border: 1px solid #e8edf2;
    }
    .offer-card { border-right: 6px solid #2a9d8f; }
    .sub-card { background: #f7f9fc; padding: 15px; border-radius: 8px; border: 1px dashed #00b4d8; }
    
    .product-link { color: #00b4d8 !important; font-weight: 700; text-decoration: none; }
    .product-link:hover { text-decoration: underline !important; }
    
    .footer { text-align: center; padding: 20px; color: #6c757d; border-top: 1px solid #e9ecef; margin-top: 40px; }
    .coupon-badge, .status-badge { display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; margin-top: 5px; }
    .coupon-enabled, .status-active { background: #d4edda; color: #155724; }
    .coupon-disabled, .status-inactive { background: #f8d7da; color: #721c24; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# دوال مساعدة موثقة ومحدثة لمعالجة الأخطاء والتواريخ حياً
# ==========================================

def safe_parse_date(date_str: Optional[str]) -> Optional[datetime]:
    if not date_str:
        return None
    date_str = str(date_str).strip()
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
        try:
            if isinstance(p, dict):
                clean_elements.append(f"• {p.get('name', 'منتج')} (SKU: {p.get('sku', 'بدون SKU')}) [ID: {p.get('id', 'بدون ID')}]")
            else:
                clean_elements.append(f"• معرف منتج رقم: {p}")
        except Exception:
            clean_elements.append("• منتج غير معرف")
    return "\n".join(clean_elements)

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
            error_detail = response.json() if response.headers.get('content-type') == 'application/json' else response.text[:500]
            st.error(f"⚠️ خطأ {response.status_code}: {error_detail}")
            return None
        return response.json()
    except Exception as e:
        st.error(f"⚠️ خطأ في الاتصال بالخادم حياً: {str(e)}")
        return None

def get_headers():
    return {
        "Authorization": f"Bearer {st.session_state.get('access_token', '')}",
        "Content-Type": "application/json"
    }

# ==========================================
# دالة معالجة استيراد الإكسيل الجماعي الفوري
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
            
            # حماية برمجية للتواريخ من خلل الثواني الزائدة
            start_date = str(row.get('Start_Date_Time', ''))
            if re.search(r':6\d$', start_date): start_date = re.sub(r':6\d$', ':59', start_date)
            expiry_date = str(row.get('Expiry_Date_Time', ''))
            if re.search(r':6\d$', expiry_date): expiry_date = re.sub(r':6\d$', ':59', expiry_date)
            
            # تحليل المنتجات المشمولة
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

# ==========================================
# دالة نموذج الإكسيل الاحترافي المكتمل بالقوائم
# ==========================================
def generate_salla_excel_template() -> bytes:
    output = io.BytesIO()
    columns = [
        "Action", "Offer_ID", "Offer_Name", "Offer_Type", "Applied_Channel",
        "Applied_To", "With_Coupon", "Offer_Status", "Start_Date_Time", "Expiry_Date_Time", 
        "Buy_Type", "Buy_Quantity", "Buy_Products_IDs", "Get_Type", "Get_Quantity", 
        "Discount_Type", "Discount_Amount", "Get_Products_IDs", "Offer_Message"
    ]
    sample_data = [
        ["create", "", "عرض ترويجي جديد", "buy_x_get_y", "browser_and_application", "product", "نعم", "active", "2026-06-22 12:00:00", "2026-07-22 23:59:59", "product", 1, "1298176905", "product", 1, "percentage", 50, "1298176905", "خصم 50% على الحبة الثانية"]
    ]
    df = pd.DataFrame(sample_data, columns=columns)
    with pd.ExcelWriter(buffer:=io.BytesIO(), engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='قائمة العروض')
        worksheet = writer.sheets['قائمة العروض']
        from openpyxl.styles import PatternFill, Font, Alignment
        header_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
        for cell in worksheet[1]:
            cell.fill = header_fill
            cell.font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
            cell.alignment = Alignment(horizontal="center", vertical="center")
        for col in worksheet.columns:
            worksheet.column_dimensions[col[0].column_letter].width = 22
    return buffer.getvalue()

# --- إدارة جلسة الدخول وأمن المنظومة ---
if "admin_password" not in st.session_state: st.session_state["admin_password"] = "admin123"
if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if "access_token" not in st.session_state: st.session_state["access_token"] = ""

if not st.session_state["logged_in"]:
    st.markdown("<div class='login-container'>", unsafe_allow_html=True)
    st.markdown("<h2 style='color:#0f1c2e; font-weight:700;'>🛡️ تسجيل دخول منظومة بلسم</h2>", unsafe_allow_html=True)
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

# --- بناء الشاشات والأقسام التنفيذية بعد الدخول المستقر ---
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

# ==========================================
# معالجة وعرض الشاشات التنفيذية
# ==========================================
if page == "📊 لوحة تصفية وإدارة العروض الحالية":
    st.markdown("<h2 style='color:#0f1c2e;'>📊 لوحة إدارة وتصفية العروض الجماعية</h2>", unsafe_allow_html=True)
    
    col_info, col_btn = st.columns([3, 1])
    with col_info: st.info("📥 قم بتنزيل النموذج الاحترافي الملون ورفع ملف الإكسيل المعبأ لتحديث المتجر حياً فورا:")
    with col_btn: st.download_button(label="📥 تحميل نموذج الإكسيل", data=generate_salla_excel_template(), file_name="Salla_Offers_Template.xlsx", use_container_width=True)
    
    uploaded_file = st.file_uploader("📂 اختر ملف العروض المعبأ للاستيراد النظيف المنسق:", type=["xlsx"])
    if uploaded_file:
        df_user = pd.read_excel(uploaded_file)
        st.dataframe(df_user, use_container_width=True) # عرض الجدول منضبط ومثالي بدون حروف مكسورة
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
            st.markdown("</div>", unsafe_allow_html=True)

elif page == "📦 مركز جرد المنتجات ومعرفات الـ IDs":
    st.markdown("<h2 style='color:#0f1c2e;'>📦 مركز جرد وحالات ظهور منتجات الصيدلية بالمتجر حياً</h2>", unsafe_allow_html=True)
    prod_res = safe_api_request("GET", "https://api.salla.dev/admin/v2/products", get_headers())
    if prod_res and "data" in prod_res:
        search_query = st.text_input("🔍 ابحث هنا بواسطة اسم المنتج أو الـ SKU لجرد البيانات والتحكم فورا:")
        for idx, p in enumerate(prod_res["data"]):
            if not search_query or search_query.lower() in p['name'].lower() or search_query.lower() in str(p.get('sku', '')).lower():
                st.markdown("<div class='product-card' style='padding:15px !important;'>", unsafe_allow_html=True)
                c1, c2, c3 = st.columns([4, 2, 2])
                with c1:
                    st.markdown(f"📦 **{p['name']}** | SKU: `{p.get('sku')}`")
                    st.caption(f"🔑 ID: `{p['id']}` | المخزون الحالي: **{p.get('quantity', 0)} حبة**")
                with c2:
                    current_status = p.get('status', 'sale')
                    btn_label = "👁️ إخفاء من المتجر" if current_status == "sale" else "👁️ إظهار بالمتجر"
                    if st.button(btn_label, key=f"p_st_{p['id']}_{idx}", use_container_width=True):
                        target_status = "hidden" if current_status == "sale" else "sale"
                        # إصلاح فني: إرسال طلب POST إلى endpoint الـ status المخصص حياً
                        safe_api_request("POST", f"https://api.salla.dev/admin/v2/products/{p['id']}/status", get_headers(), json={"status": target_status})
                        st.rerun()
                with c3:
                    if st.button("📋 نسخ ID المنتج", key=f"p_cp_{p['id']}_{idx}", use_container_width=True):
                        st.toast(f"✅ تم نسخ المعرف: {p['id']}")
                st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<div class='footer'><p>© 2026 منظومة بلسم الرقمية لإدارة العروض | صيدليات بلسم العُلا الموثقة</p></div>", unsafe_allow_html=True)
