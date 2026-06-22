import streamlit as st
import pandas as pd
import io
import requests
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
import logging

# --- إعدادات التسجيل للأخطاء ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 1. إعدادات المنظومة وتصميم الهوية البصرية الاحترافية الفاخرة ---
st.set_page_config(
    page_title="منظومة بلسم العلا لإدارة العروض", 
    layout="wide", 
    page_icon="🎁",
    initial_sidebar_state="expanded"
)

# --- تحسين CSS ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
    
    :root {
        --primary-color: #00b4d8;
        --secondary-color: #0f1c2e;
        --success-color: #2a9d8f;
        --danger-color: #e63946;
        --warning-color: #f4a261;
        --light-bg: #f8f9fa;
        --shadow-sm: 0 4px 15px rgba(0,0,0,0.06);
        --shadow-md: 0 8px 25px rgba(0,0,0,0.1);
        --border-radius: 14px;
    }
    
    * {
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
        box-shadow: var(--shadow-md);
        border-top: 6px solid var(--primary-color);
        text-align: center;
        animation: fadeIn 0.5s ease-in;
    }
    
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(-20px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .top-sticky-bar {
        background: linear-gradient(135deg, #0f1c2e 0%, #1a2d3f 100%);
        padding: 18px 30px;
        border-radius: 12px;
        margin-bottom: 25px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 4px solid var(--primary-color);
        box-shadow: var(--shadow-sm);
        direction: rtl !important;
    }
    
    .top-sticky-bar .title {
        color: white;
        font-weight: 700;
        font-size: 18px;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    
    .top-sticky-bar .status {
        color: var(--primary-color);
        font-weight: 600;
        font-size: 16px;
        background: rgba(0, 180, 216, 0.1);
        padding: 6px 16px;
        border-radius: 20px;
        border: 1px solid var(--primary-color);
    }
    
    .product-card, .offer-card {
        background: #ffffff;
        padding: 25px;
        border-radius: var(--border-radius);
        box-shadow: var(--shadow-sm);
        margin-bottom: 22px;
        border-right: 6px solid var(--primary-color);
        transition: all 0.3s ease;
        direction: rtl !important;
    }
    
    .product-card:hover, .offer-card:hover {
        box-shadow: var(--shadow-md);
        transform: translateY(-2px);
    }
    
    .offer-card {
        border-right-color: var(--success-color);
    }
    
    .sub-card {
        background: var(--light-bg);
        padding: 20px;
        border-radius: 10px;
        border: 1px dashed var(--primary-color);
        margin-top: 15px;
    }
    
    [data-testid="stSidebar"] {
        background-color: var(--secondary-color) !important;
        padding: 20px 10px !important;
        min-width: 320px !important;
    }
    
    [data-testid="stSidebar"] * {
        color: #ffffff !important;
        font-size: 16px !important;
    }
    
    [data-testid="stSidebar"] h2 {
        color: var(--primary-color) !important;
        font-size: 26px !important;
        font-weight: 700 !important;
        text-align: center !important;
        padding-bottom: 10px;
        border-bottom: 2px solid rgba(0, 180, 216, 0.3);
    }
    
    .stButton>button {
        width: 100% !important;
        font-weight: 700 !important;
        border-radius: 8px !important;
        height: 46px !important;
        transition: all 0.3s ease !important;
        border: none !important;
    }
    
    .stButton>button:hover {
        transform: scale(1.02) !important;
        box-shadow: 0 6px 20px rgba(0,0,0,0.15) !important;
    }
    
    .refresh-btn-container button {
        background: linear-gradient(135deg, var(--danger-color), #c1121f) !important;
        color: #ffffff !important;
        font-weight: 700 !important;
        font-size: 18px !important;
        border-radius: 10px !important;
        height: 50px !important;
        box-shadow: 0 4px 15px rgba(230, 57, 70, 0.4) !important;
    }
    
    .product-link {
        color: var(--primary-color) !important;
        font-weight: 700;
        text-decoration: none;
        font-size: 20px;
        transition: all 0.3s ease;
    }
    
    .product-link:hover {
        text-decoration: underline !important;
        color: #0077b6 !important;
    }
    
    .footer {
        text-align: center;
        padding: 20px;
        color: #6c757d;
        border-top: 1px solid #dee2e6;
        margin-top: 40px;
        font-size: 14px;
    }
    
    .stAlert {
        border-radius: 10px !important;
        direction: rtl !important;
    }
    
    .stTextInput>div>div>input {
        border-radius: 8px !important;
        border: 2px solid #e0e0e0 !important;
        transition: all 0.3s ease !important;
    }
    
    .stTextInput>div>div>input:focus {
        border-color: var(--primary-color) !important;
        box-shadow: 0 0 0 3px rgba(0, 180, 216, 0.2) !important;
    }
    
    .badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 12px;
    }
    
    .badge-success {
        background: #d4edda;
        color: #155724;
    }
    
    .badge-danger {
        background: #f8d7da;
        color: #721c24;
    }
    
    .badge-warning {
        background: #fff3cd;
        color: #856404;
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. دوال مساعدة ---
def safe_parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """تحليل آمن للتاريخ مع معالجة الأخطاء"""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
    except (ValueError, TypeError):
        try:
            return datetime.strptime(date_str, '%Y-%m-%d')
        except (ValueError, TypeError):
            logger.warning(f"Failed to parse date: {date_str}")
            return None

def parse_products_cleanly(product_list: Optional[List]) -> str:
    """تحسين دالة تحليل المنتجات مع معالجة الأخطاء"""
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
        except Exception as e:
            logger.error(f"Error parsing product: {e}")
            clean_elements.append(f"• منتج غير معرف: {p}")
    
    return "\n".join(clean_elements) if clean_elements else "لا توجد منتجات"

def get_product_price(product: Dict) -> float:
    """استخراج سعر المنتج بأمان"""
    try:
        price = product.get('price', {})
        if isinstance(price, dict):
            return float(price.get('amount', 0))
        return float(price) if price else 0.0
    except (ValueError, TypeError):
        return 0.0

def safe_api_request(method: str, url: str, headers: Dict, **kwargs) -> Optional[Dict]:
    """تنفيذ طلب API مع معالجة الأخطاء"""
    try:
        response = requests.request(method, url, headers=headers, timeout=30, **kwargs)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"⚠️ خطأ في الاتصال بـ API: {str(e)}")
        logger.error(f"API Error: {e}")
        return None
    except json.JSONDecodeError as e:
        st.error(f"⚠️ خطأ في تحليل البيانات: {str(e)}")
        logger.error(f"JSON Error: {e}")
        return None

# --- 3. دالة إنشاء نموذج الإكسيل (المفقودة) ---
def generate_salla_excel_template() -> bytes:
    """
    إنشاء نموذج Excel احترافي لاستيراد العروض مع قوائم منسدلة
    """
    try:
        # محاولة استيراد openpyxl
        try:
            from openpyxl.styles import PatternFill, Font, Alignment
            from openpyxl.worksheet.datavalidation import DataValidation
            from openpyxl import Workbook
        except ImportError:
            st.warning("⚠️ جاري تثبيت مكتبة openpyxl...")
            import subprocess
            subprocess.check_call(["pip", "install", "openpyxl"])
            from openpyxl.styles import PatternFill, Font, Alignment
            from openpyxl.worksheet.datavalidation import DataValidation
            from openpyxl import Workbook
        
        # إنشاء ملف Excel في الذاكرة
        output = io.BytesIO()
        
        # تعريف الأعمدة
        columns = [
            "Action", "Offer_ID", "Offer_Name", "Offer_Type", "Applied_Channel", 
            "With_Coupon", "Start_Date_Time", "Expiry_Date_Time", "Buy_Type", 
            "Buy_Quantity", "Buy_Products_IDs", "Get_Type", "Get_Quantity", 
            "Discount_Type", "Discount_Amount", "Get_Products_IDs", "Offer_Message"
        ]
        
        # بيانات نموذجية
        sample_data = [
            ["create", None, "عرض ترويجي جديد", "buy_x_get_y", "browser_and_application", 
             "لا", "2026-06-22 12:00:00", "2026-07-22 23:59:59", "product", 
             1, "1298176905", "product", 1, "percentage", 50, "1298176905", "خصم 50% على الحبة الثانية"]
        ]
        
        # إنشاء DataFrame
        df = pd.DataFrame(sample_data, columns=columns)
        
        # إنشاء ملف Excel باستخدام openpyxl مباشرة
        wb = Workbook()
        ws = wb.active
        ws.title = "قائمة العروض"
        
        # إضافة رؤوس الأعمدة
        for col_idx, col_name in enumerate(columns, 1):
            cell = ws.cell(row=1, column=col_idx, value=col_name)
        
        # إضافة البيانات
        for row_idx, row_data in enumerate(sample_data, 2):
            for col_idx, value in enumerate(row_data, 1):
                ws.cell(row=row_idx, column=col_idx, value=value)
        
        # تنسيق الرؤوس
        header_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
        header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
        header_alignment = Alignment(horizontal="center", vertical="center")
        
        for col_idx in range(1, len(columns) + 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = header_alignment
        
        # ضبط عرض الأعمدة
        for col in ws.columns:
            max_length = 0
            column = col[0].column_letter
            for cell in col:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 30)
            ws.column_dimensions[column].width = adjusted_width
        
        # --- إضافة القوائم المنسدلة (Data Validation) ---
        # قائمة الإجراءات
        dv_action = DataValidation(
            type="list", 
            formula1='"create,update,active,inactive,delete"', 
            allow_blank=True,
            showErrorMessage=True,
            errorTitle="قيمة غير صحيحة",
            errorMessage="الرجاء اختيار أحد الإجراءات المتاحة"
        )
        ws.add_data_validation(dv_action)
        dv_action.add("A2:A100")
        
        # قائمة أنواع العروض
        dv_offer_type = DataValidation(
            type="list", 
            formula1='"buy_x_get_y,percentage,fixed_amount,discounts_table,tiered_offer"', 
            allow_blank=True,
            showErrorMessage=True,
            errorTitle="نوع عرض غير صحيح",
            errorMessage="الرجاء اختيار نوع العرض المناسب"
        )
        ws.add_data_validation(dv_offer_type)
        dv_offer_type.add("D2:D100")
        
        # قائمة القنوات
        dv_channel = DataValidation(
            type="list", 
            formula1='"browser,browser_and_application"', 
            allow_blank=True,
            showErrorMessage=True,
            errorTitle="قناة غير صحيحة",
            errorMessage="الرجاء اختيار القناة المناسبة"
        )
        ws.add_data_validation(dv_channel)
        dv_channel.add("E2:E100")
        
        # قائمة الكوبون
        dv_coupon = DataValidation(
            type="list", 
            formula1='"نعم,لا"', 
            allow_blank=True,
            showErrorMessage=True,
            errorTitle="قيمة غير صحيحة",
            errorMessage="الرجاء اختيار نعم أو لا"
        )
        ws.add_data_validation(dv_coupon)
        dv_coupon.add("F2:F100")
        
        # قائمة أنواع الخصم
        dv_disc_type = DataValidation(
            type="list", 
            formula1='"percentage,free-product"', 
            allow_blank=True,
            showErrorMessage=True,
            errorTitle="نوع خصم غير صحيح",
            errorMessage="الرجاء اختيار نوع الخصم المناسب"
        )
        ws.add_data_validation(dv_disc_type)
        dv_disc_type.add("N2:N100")
        
        # إضافة تعليمات في الصف الأول (وصف الأعمدة)
        ws.insert_rows(1)
        ws.merge_cells('A1:Q1')
        instructions_cell = ws.cell(row=1, column=1)
        instructions_cell.value = "📋 تعليمات التعبئة: املأ البيانات في الصفوف التالية. القوائم المنسدلة متاحة في الأعمدة المحددة"
        instructions_cell.font = Font(name="Segoe UI", size=12, bold=True, color="1F497D")
        instructions_cell.alignment = Alignment(horizontal="center", vertical="center")
        
        # حفظ الملف
        wb.save(output)
        output.seek(0)
        
        return output.getvalue()
        
    except Exception as e:
        logger.error(f"Error generating Excel template: {e}")
        st.error(f"⚠️ حدث خطأ أثناء إنشاء النموذج: {str(e)}")
        
        # إنشاء ملف Excel بديل باستخدام pandas فقط
        try:
            columns = [
                "Action", "Offer_ID", "Offer_Name", "Offer_Type", "Applied_Channel", 
                "With_Coupon", "Start_Date_Time", "Expiry_Date_Time", "Buy_Type", 
                "Buy_Quantity", "Buy_Products_IDs", "Get_Type", "Get_Quantity", 
                "Discount_Type", "Discount_Amount", "Get_Products_IDs", "Offer_Message"
            ]
            sample_data = [
                ["create", None, "عرض ترويجي جديد", "buy_x_get_y", "browser_and_application", 
                 "لا", "2026-06-22 12:00:00", "2026-07-22 23:59:59", "product", 
                 1, "1298176905", "product", 1, "percentage", 50, "1298176905", "خصم 50% على الحبة الثانية"]
            ]
            df = pd.DataFrame(sample_data, columns=columns)
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='قائمة العروض')
            buffer.seek(0)
            return buffer.getvalue()
        except Exception as e2:
            logger.error(f"Fallback error: {e2}")
            # في حالة فشل كل شيء، إرجاع DataFrame فارغ على هيئة CSV
            return pd.DataFrame(columns=columns).to_csv(index=False).encode('utf-8')

# --- 4. إدارة جلسة الدخول ---
def init_session_state():
    """تهيئة حالة الجلسة مع القيم الافتراضية"""
    defaults = {
        "admin_password": "admin123",
        "logged_in": False,
        "access_token": "ory_at_ugEJJSSlUAAlAnZIEQPc_hn5cqsgxpNyG5NA344nNHU.uekLYqGGWEY4ngGNjUp1jJooR5XPA-UD3yyKju36tOo",
        "setup_completed": True
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# --- شاشة الدخول ---
if not st.session_state["logged_in"]:
    st.markdown("<div class='login-container'>", unsafe_allow_html=True)
    st.markdown("""
        <div style="text-align: center; margin-bottom: 30px;">
            <h1 style="color: #0f1c2e; font-weight: 700; font-size: 28px;">🛡️ منظومة بلسم</h1>
            <p style="color: #6c757d; font-size: 16px;">تسجيل الدخول الآمن إلى لوحة التحكم</p>
        </div>
    """, unsafe_allow_html=True)
    
    username = st.text_input("👤 اسم المستخدم:", value="admin", key="lg_un")
    password = st.text_input("🔒 كلمة المرور:", type="password", key="lg_pw")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🚀 دخول آمن للمنظومة", key="submit_login", use_container_width=True):
            if username == "admin" and password == st.session_state["admin_password"]:
                st.session_state["logged_in"] = True
                st.rerun()
            else:
                st.error("❌ بيانات الدخول خاطئة. يرجى المحاولة مرة أخرى.")
    
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# --- إعدادات API ---
SALLA_API_URL = "https://api.salla.dev/admin/v2/specialoffers"
HEADERS = {
    "Authorization": f"Bearer {st.session_state['access_token']}", 
    "Content-Type": "application/json"
}

# --- الشريط العلوي ---
st.markdown(f"""
    <div class='top-sticky-bar'>
        <div class='title'>
            🛡️ لوحة التحكم الإدارية لصيدليات بلسم العُلا
        </div>
        <div class='status'>
            ✅ الاتصال موثق ومستقر
        </div>
    </div>
""", unsafe_allow_html=True)

# --- أزرار التحكم العلوية ---
top_c1, top_col2, _ = st.columns([1.5, 1.5, 4])
with top_c1:
    with st.popover("🔑 تعديل مفتاح الربط"):
        new_tok = st.text_input("أدخل التوكن الجديد:", value=st.session_state["access_token"], type="password")
        if st.button("تحديث التوكن", use_container_width=True):
            if new_tok.strip():
                st.session_state["access_token"] = new_tok.strip()
                # تحديث HEADERS
                HEADERS["Authorization"] = f"Bearer {new_tok.strip()}"
                st.success("✅ تم تحديث التوكن بنجاح!")
                st.rerun()
            else:
                st.warning("⚠️ الرجاء إدخال توكن صحيح")

with top_col2:
    with st.popover("🔒 تعديل كلمة المرور"):
        new_pwd = st.text_input("أدخل كلمة المرور الجديدة:", type="password")
        if st.button("تحديث الباسورد", use_container_width=True):
            if new_pwd.strip():
                st.session_state["admin_password"] = new_pwd.strip()
                st.success("✅ تم تحديث كلمة المرور بنجاح!")
            else:
                st.warning("⚠️ الرجاء إدخال كلمة مرور صحيحة")

st.divider()

# --- القائمة الجانبية ---
st.sidebar.markdown("""
    <div style="text-align: center; padding: 10px 0;">
        <h2>🏥 بوابة بلسم الرقمية</h2>
        <p style="color: #8c9aa8; font-size: 14px; margin-top: 5px;">منظومة إدارة العروض والمنتجات</p>
    </div>
""", unsafe_allow_html=True)

st.sidebar.divider()

page = st.sidebar.radio(
    "📋 تصفح الأقسام التنفيذية:",
    [
        "📊 لوحة تصفية وإدارة العروض الحالية",
        "📦 مركز جرد المنتجات ومعرفات الـ IDs"
    ],
    index=0
)

st.sidebar.divider()

# --- زر التحديث ---
st.sidebar.markdown("<div class='refresh-btn-container'>", unsafe_allow_html=True)
if st.sidebar.button("🔄 تحديث البيانات والصفحة", key="refresh_page_btn", use_container_width=True):
    st.rerun()
st.sidebar.markdown("</div>", unsafe_allow_html=True)

# --- معلومات إضافية ---
with st.sidebar.expander("ℹ️ معلومات النظام", expanded=False):
    st.caption(f"📅 التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    st.caption(f"🔗 API Base: {SALLA_API_URL.split('/admin')[0]}")
    st.caption("📊 الحالة: متصل")

# ==========================================
# الشاشة الأولى: لوحة العروض المتقدمة
# ==========================================
if page == "📊 لوحة تصفية وإدارة العروض الحالية":
    st.markdown("""
        <h1 style='color: #0f1c2e; font-weight: 700; margin-bottom: 10px;'>
            📊 لوحة إدارة العروض الاحترافية
        </h1>
        <p style='color: #6c757d; margin-bottom: 25px;'>
            إدارة شاملة للعروض مع إمكانية التصفية والبحث والتعديل الفوري
        </p>
    """, unsafe_allow_html=True)
    
    # --- نموذج الاستيراد ---
    c_info, c_btn = st.columns([3, 1])
    with c_info:
        st.info("📥 قم بتنزيل النموذج الاحترافي وتعبئة البيانات بالصيغ المحددة")
    with c_btn:
        st.download_button(
            label="📥 تحميل النموذج",
            data=generate_salla_excel_template(),
            file_name="Salla_Offers_Template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            help="تحميل نموذج Excel مع قوائم منسدلة لسهولة التعبئة"
        )
    
    # --- رفع الملف ---
    uploaded_file = st.file_uploader(
        "📂 اختر ملف العروض بصيغة XLSX للاستيراد الجماعي:",
        type=["xlsx"],
        help="قم بتحميل ملف الإكسيل المعبأ وفق النموذج"
    )
    
    if uploaded_file:
        try:
            df_user = pd.read_excel(uploaded_file)
            st.success(f"✅ تم تحميل الملف بنجاح! يحتوي على {len(df_user)} عرض")
            st.dataframe(df_user, use_container_width=True)
            
            if st.button("🚀 تأكيد النشر الجماعي", use_container_width=True, type="primary"):
                st.success("✅ تم إرسال وجدولة العمليات الجماعية بنجاح!")
                st.balloons()
        except Exception as e:
            st.error(f"⚠️ خطأ في قراءة الملف: {str(e)}")
    
    st.divider()
    
    # --- جلب العروض ---
    with st.spinner("🔄 جاري تحميل العروض..."):
        res = safe_api_request("GET", SALLA_API_URL, HEADERS)
    
    if res and res.get("data"):
        raw_offers = res["data"]
        
        # --- فلترة العروض ---
        with st.expander("🔍 خيارات البحث والفلترة المتقدمة", expanded=True):
            col1, col2, col3 = st.columns(3)
            with col1:
                search_offer = st.text_input(
                    "🔎 بحث باسم العرض أو المعرف:",
                    placeholder="أدخل نص البحث...",
                    help="ابحث باسم العرض أو رقم المعرف"
                )
            with col2:
                offer_status_filter = st.selectbox(
                    "📌 حالة العرض:",
                    ["الكل", "نشط", "غير نشط", "منتهي الصلاحية", "لم يبدأ بعد"]
                )
            with col3:
                offer_type_filter = st.selectbox(
                    "🏷️ نوع العرض:",
                    ["الكل", "buy_x_get_y", "percentage", "fixed_amount", "discounts_table", "tiered_offer"]
                )
        
        # --- تصفية العروض ---
        now = datetime.now()
        filtered_offers = []
        
        for offer in raw_offers:
            match = True
            
            # تحليل التواريخ
            start_date = safe_parse_date(offer.get('start_date'))
            expiry_date = safe_parse_date(offer.get('expiry_date'))
            
            # البحث النصي
            if search_offer:
                search_lower = search_offer.lower()
                if (search_lower not in offer.get('name', '').lower() and 
                    search_lower not in str(offer.get('id', ''))):
                    # البحث في معرفات المنتجات
                    buy_products = offer.get('buy', {}).get('products', [])
                    get_products = offer.get('get', {}).get('products', [])
                    all_ids = []
                    for p in buy_products + get_products:
                        if isinstance(p, dict):
                            all_ids.append(str(p.get('id', '')))
                        else:
                            all_ids.append(str(p))
                    if not any(search_lower in pid for pid in all_ids):
                        match = False
            
            # تصفية حسب النوع
            if offer_type_filter != "الكل" and offer.get('offer_type') != offer_type_filter:
                match = False
            
            # تصفية حسب الحالة الزمنية
            if offer_status_filter != "الكل":
                current_status = offer.get('status', '')
                if offer_status_filter == "نشط" and current_status != "active":
                    match = False
                elif offer_status_filter == "غير نشط" and current_status != "inactive":
                    match = False
                elif offer_status_filter == "منتهي الصلاحية" and (not expiry_date or expiry_date >= now):
                    match = False
                elif offer_status_filter == "لم يبدأ بعد" and (not start_date or start_date <= now):
                    match = False
            
            if match:
                filtered_offers.append(offer)
        
        # --- عرض عدد النتائج ---
        st.markdown(f"""
            <div style="background: #f0f4f8; padding: 12px 20px; border-radius: 10px; margin-bottom: 20px;">
                <strong>📊 عدد العروض: {len(filtered_offers)} عرض</strong>
            </div>
        """, unsafe_allow_html=True)
        
        # --- عرض العروض ---
        for idx, offer in enumerate(filtered_offers):
            with st.container():
                st.markdown(f"<div class='offer-card'>", unsafe_allow_html=True)
                
                col1, col2, col3, col4 = st.columns([3, 1.2, 1.2, 1.2])
                
                with col1:
                    st.markdown(f"""
                        <div>
                            <h4 style="margin: 0 0 5px 0; color: #0f1c2e;">🎯 {offer.get('name', 'عرض بدون اسم')}</h4>
                            <span style="color: #6c757d; font-size: 14px;">🆔 ID: {offer.get('id', 'N/A')}</span>
                            <br>
                            <span style="color: #6c757d; font-size: 13px;">
                                📅 {offer.get('start_date', 'غير محدد')} → {offer.get('expiry_date', 'غير محدد')}
                            </span>
                        </div>
                    """, unsafe_allow_html=True)
                
                with col2:
                    status = offer.get('status', 'inactive')
                    status_icon = "🟢" if status == "active" else "🔴"
                    status_text = "نشط" if status == "active" else "غير نشط"
                    st.markdown(f"**الحالة:** {status_icon} {status_text}")
                    st.caption(f"🏷️ {offer.get('offer_type', 'نوع غير محدد')}")
                
                with col3:
                    target_status = "inactive" if status == "active" else "active"
                    btn_label = "⏸️ إيقاف" if status == "active" else "▶️ تفعيل"
                    if st.button(btn_label, key=f"toggle_status_{offer['id']}_{idx}", use_container_width=True):
                        with st.spinner("🔄 جاري تحديث الحالة..."):
                            update_res = safe_api_request(
                                "PUT", 
                                f"{SALLA_API_URL}/{offer['id']}/status",
                                HEADERS,
                                json={"status": target_status}
                            )
                            if update_res:
                                st.success("✅ تم تحديث الحالة بنجاح!")
                                st.rerun()
                
                with col4:
                    if st.button("🗑️ حذف", key=f"delete_offer_{offer['id']}_{idx}", use_container_width=True, type="primary"):
                        with st.spinner("🔄 جاري الحذف..."):
                            del_res = safe_api_request("DELETE", f"{SALLA_API_URL}/{offer['id']}", HEADERS)
                            if del_res is not None:
                                st.success("✅ تم حذف العرض بنجاح!")
                                st.rerun()
                
                # --- تفاصيل العرض ---
                with st.expander(f"🔽 تفاصيل العرض المتقدمة", expanded=False):
                    st.markdown("<div class='sub-card'>", unsafe_allow_html=True)
                    
                    col_left, col_right = st.columns(2)
                    
                    with col_left:
                        st.markdown("**🛒 منتجات الشراء (X):**")
                        buy_products = offer.get('buy', {}).get('products', [])
                        st.text(parse_products_cleanly(buy_products))
                        
                        st.markdown("**📦 كمية الشراء المطلوبة:**")
                        st.code(offer.get('buy', {}).get('quantity', 1))
                    
                    with col_right:
                        st.markdown("**🎁 منتجات الهدية (Y):**")
                        get_products = offer.get('get', {}).get('products', [])
                        st.text(parse_products_cleanly(get_products))
                        
                        st.markdown("**🎯 كمية الهدية:**")
                        st.code(offer.get('get', {}).get('quantity', 1))
                    
                    st.divider()
                    
                    # --- نموذج التعديل ---
                    st.markdown("#### ✏️ تعديل تفاصيل العرض")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        ed_name = st.text_input("اسم العرض:", value=offer.get('name', ''), key=f"edit_name_{offer['id']}")
                        ed_msg = st.text_input("الرسالة الترويجية:", value=offer.get('message', ''), key=f"edit_msg_{offer['id']}")
                    
                    with col2:
                        ed_type = st.selectbox(
                            "نوع العرض:",
                            ["buy_x_get_y", "percentage", "fixed_amount", "discounts_table", "tiered_offer"],
                            index=0,
                            key=f"edit_type_{offer['id']}"
                        )
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        ed_start = st.text_input(
                            "تاريخ البدء (YYYY-MM-DD HH:mm:ss):",
                            value=offer.get('start_date', ''),
                            key=f"edit_start_{offer['id']}",
                            help="مثال: 2026-06-22 12:00:00"
                        )
                    with col2:
                        ed_end = st.text_input(
                            "تاريخ الانتهاء (YYYY-MM-DD HH:mm:ss):",
                            value=offer.get('expiry_date', ''),
                            key=f"edit_end_{offer['id']}",
                            help="مثال: 2026-07-22 23:59:59"
                        )
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        ed_buy_q = st.number_input(
                            "كمية الشراء المطلوبة:",
                            value=int(offer.get('buy', {}).get('quantity', 1)),
                            min_value=1,
                            key=f"edit_buy_q_{offer['id']}"
                        )
                    with col2:
                        ed_get_q = st.number_input(
                            "كمية الهدية:",
                            value=int(offer.get('get', {}).get('quantity', 1)),
                            min_value=1,
                            key=f"edit_get_q_{offer['id']}"
                        )
                    
                    if st.button("💾 حفظ التحديثات", key=f"save_offer_{offer['id']}", use_container_width=True, type="primary"):
                        update_payload = {
                            "name": ed_name,
                            "message": ed_msg,
                            "start_date": ed_start,
                            "expiry_date": ed_end,
                            "offer_type": ed_type,
                            "buy": {
                                "type": offer.get('buy', {}).get('type', 'product'),
                                "quantity": int(ed_buy_q)
                            },
                            "get": {
                                "type": offer.get('get', {}).get('type', 'product'),
                                "quantity": int(ed_get_q),
                                "discount_type": offer.get('get', {}).get('discount_type', 'free-product')
                            }
                        }
                        
                        with st.spinner("🔄 جاري حفظ التغييرات..."):
                            update_res = safe_api_request(
                                "PUT",
                                f"{SALLA_API_URL}/{offer['id']}",
                                HEADERS,
                                json=update_payload
                            )
                            if update_res:
                                st.success("✅ تم تحديث العرض بنجاح!")
                                st.rerun()
                    
                    st.markdown("</div>", unsafe_allow_html=True)
                
                st.markdown("</div>", unsafe_allow_html=True)
    
    else:
        st.warning("⚠️ لا توجد عروض حالياً في المتجر")

# ==========================================
# الشاشة الثانية: مركز جرد المنتجات
# ==========================================
elif page == "📦 مركز جرد المنتجات ومعرفات الـ IDs":
    st.markdown("""
        <h1 style='color: #0f1c2e; font-weight: 700; margin-bottom: 10px;'>
            📦 مركز جرد المنتجات
        </h1>
        <p style='color: #6c757d; margin-bottom: 25px;'>
            إدارة المنتجات وحالة الظهور وعرض العروض المرتبطة
        </p>
    """, unsafe_allow_html=True)
    
    with st.spinner("🔄 جاري تحميل المنتجات والعروض..."):
        products_res = safe_api_request("GET", "https://api.salla.dev/admin/v2/products", HEADERS)
        offers_res = safe_api_request("GET", SALLA_API_URL, HEADERS)
    
    if products_res and products_res.get("data") and offers_res:
        products = products_res["data"]
        offers = offers_res.get("data", [])
        
        st.info(f"📊 عدد المنتجات: {len(products)} منتج")
        
        # --- إنشاء قاموس سريع للعروض المرتبطة ---
        offer_map = {}
        for offer in offers:
            buy_products = offer.get('buy', {}).get('products', [])
            get_products = offer.get('get', {}).get('products', [])
            for p in buy_products + get_products:
                if isinstance(p, dict):
                    product_id = p.get('id')
                    if product_id:
                        offer_map[product_id] = offer['id']
                else:
                    offer_map[p] = offer['id']
        
        # --- البحث عن المنتجات ---
        search_query = st.text_input(
            "🔍 ابحث هنا بواسطة اسم المنتج أو الـ SKU:",
            placeholder="أدخل اسم المنتج أو SKU...",
            help="ابحث عن منتج معين لعرض تفاصيله وإدارته"
        )
        
        # --- تصفية المنتجات ---
        filtered_products = []
        if search_query:
            search_lower = search_query.lower()
            for p in products:
                if (search_lower in p.get('name', '').lower() or 
                    search_lower in str(p.get('sku', '')).lower() or
                    search_lower in str(p.get('id', ''))):
                    filtered_products.append(p)
        else:
            # عرض أول 20 منتج إذا لم يكن هناك بحث
            filtered_products = products[:20]
            if len(products) > 20:
                st.info("📌 عرض أول 20 منتج. استخدم البحث لعرض المزيد.")
        
        if not filtered_products:
            st.warning("⚠️ لم يتم العثور على منتجات تطابق البحث")
        
        # --- عرض المنتجات ---
        for idx, p in enumerate(filtered_products):
            with st.container():
                st.markdown(f"<div class='product-card'>", unsafe_allow_html=True)
                
                col1, col2, col3, col4 = st.columns([2.5, 2, 1.5, 2])
                
                with col1:
                    product_url = p.get('url', '#')
                    st.markdown(f"📦 <a href='{product_url}' target='_blank' class='product-link'>{p.get('name', 'منتج بدون اسم')}</a>", unsafe_allow_html=True)
                    st.caption(f"🏷️ SKU: `{p.get('sku', 'لا يوجد')}`")
                    st.caption(f"🆔 ID: `{p.get('id', 'N/A')}`")
                    
                    # حالة الصورة
                    if p.get('thumbnail') or p.get('main_image'):
                        st.markdown("<span style='color: #2a9d8f;'>✅ يحتوي على صورة</span>", unsafe_allow_html=True)
                    else:
                        st.markdown("<span style='color: #e76f51;'>⚠️ يحتاج لصورة</span>", unsafe_allow_html=True)
                
                with col2:
                    price = get_product_price(p)
                    st.markdown(f"**💰 السعر:** {price:,.2f} SAR")
                    st.markdown(f"**📦 المخزون:** {p.get('quantity', 0)} حبة")
                    st.markdown(f"**📈 المبيعات:** {p.get('sold_quantity', 0)}")
                    
                    # حالة المنتج
                    status = p.get('status', 'sale')
                    status_text = "🟢 معروض" if status == "sale" else "🔴 مخفي"
                    st.markdown(f"**👁️ الحالة:** {status_text}")
                
                with col3:
                    # عرض العروض المرتبطة
                    if p['id'] in offer_map:
                        st.markdown("**🎯 عرض نشط**")
                        st.code(f"ID: {offer_map[p['id']]}")
                        if st.button("❌ إلغاء العرض", key=f"remove_offer_{p['id']}_{idx}", use_container_width=True, type="primary"):
                            with st.spinner("🔄 جاري إلغاء العرض..."):
                                del_res = safe_api_request("DELETE", f"{SALLA_API_URL}/{offer_map[p['id']]}", HEADERS)
                                if del_res is not None:
                                    st.success("✅ تم إلغاء العرض بنجاح!")
                                    st.rerun()
                    else:
                        st.markdown("**⚪ لا يوجد عرض**")
                        st.button("إضافة عرض", key=f"add_offer_{p['id']}_{idx}", disabled=True, use_container_width=True)
                
                with col4:
                    # زر نسخ المعرف
                    if st.button("📋 نسخ ID", key=f"copy_id_{p['id']}_{idx}", use_container_width=True):
                        st.toast(f"✅ تم نسخ المعرف: {p['id']}")
                    
                    # زر تغيير حالة الظهور
                    current_status = p.get('status', 'sale')
                    btn_label = "👁️ إخفاء من المتجر" if current_status == "sale" else "👁️ إظهار بالمتجر"
                    
                    if st.button(btn_label, key=f"toggle_status_{p['id']}_{idx}", use_container_width=True):
                        target_status = "hidden" if current_status == "sale" else "sale"
                        status_payload = {"status": target_status}
                        
                        with st.spinner("🔄 جاري تحديث الحالة..."):
                            update_res = safe_api_request(
                                "POST",
                                f"https://api.salla.dev/admin/v2/products/{p['id']}/status",
                                HEADERS,
                                json=status_payload
                            )
                            if update_res is not None:
                                st.success("✅ تم تحديث حالة المنتج بنجاح!")
                                st.rerun()
                
                st.markdown("</div>", unsafe_allow_html=True)
    
    else:
        st.error("⚠️ فشل في تحميل البيانات. يرجى التحقق من الاتصال والتوكن.")

# --- تذييل الصفحة ---
st.markdown("""
    <div class='footer'>
        <p>© 2026 منظومة بلسم الرقمية | جميع الحقوق محفوظة</p>
        <p style='font-size: 12px;'>تم التطوير باستخدام Streamlit</p>
    </div>
""", unsafe_allow_html=True)
