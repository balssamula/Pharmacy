import streamlit as st
import pandas as pd
import io
import requests
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
import logging
import traceback

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
# CSS المحسّن بالكامل
# ==========================================
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
    
    * {
        font-family: 'Cairo', sans-serif !important;
        direction: rtl !important;
        text-align: right !important;
        box-sizing: border-box !important;
    }
    
    /* ---------- شاشة الدخول ---------- */
    .login-container {
        max-width: 450px;
        margin: 80px auto;
        background: #ffffff;
        padding: 45px 35px;
        border-radius: 20px;
        box-shadow: 0 8px 30px rgba(0,0,0,0.12);
        border-top: 6px solid #00b4d8;
        text-align: center;
        animation: fadeIn 0.5s ease-in;
    }
    
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(-20px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    /* ---------- الشريط العلوي ---------- */
    .top-sticky-bar {
        background: linear-gradient(135deg, #0a1628 0%, #1a2d4a 100%);
        padding: 16px 28px;
        border-radius: 12px;
        margin-bottom: 25px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 4px solid #00b4d8;
        box-shadow: 0 4px 15px rgba(0,0,0,0.08);
        direction: rtl !important;
        flex-wrap: wrap;
        gap: 10px;
    }
    
    .top-sticky-bar .title {
        color: #ffffff;
        font-weight: 700;
        font-size: 17px;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    
    .top-sticky-bar .status {
        color: #00b4d8;
        font-weight: 600;
        font-size: 14px;
        background: rgba(0, 180, 216, 0.12);
        padding: 5px 16px;
        border-radius: 20px;
        border: 1px solid rgba(0, 180, 216, 0.3);
    }
    
    /* ---------- البطاقات المحسّنة ---------- */
    .product-card {
        background: #ffffff;
        padding: 0 !important;
        border-radius: 14px;
        box-shadow: 0 2px 12px rgba(0,0,0,0.07);
        margin-bottom: 20px;
        border: 1px solid #e8edf2;
        direction: rtl !important;
        overflow: hidden;
        transition: all 0.3s ease;
        position: relative;
    }
    
    .product-card:hover {
        box-shadow: 0 6px 25px rgba(0,0,0,0.1);
        transform: translateY(-2px);
    }
    
    /* رأس البطاقة مع العنوان الترويجي */
    .product-card-header {
        background: linear-gradient(135deg, #0f1c2e 0%, #1a2d4a 100%);
        padding: 14px 24px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 3px solid #00b4d8;
        direction: rtl !important;
        flex-wrap: wrap;
        gap: 8px;
    }
    
    .product-card-header .product-name {
        color: #ffffff;
        font-size: 18px;
        font-weight: 700;
        margin: 0;
    }
    
    .product-card-header .product-promotion {
        color: #ffd700;
        font-size: 14px;
        font-weight: 600;
        background: rgba(255, 215, 0, 0.15);
        padding: 4px 14px;
        border-radius: 20px;
        border: 1px solid rgba(255, 215, 0, 0.3);
        display: inline-block;
    }
    
    .product-card-body {
        padding: 18px 24px;
        direction: rtl !important;
    }
    
    /* بطاقات العروض المحسّنة */
    .offer-card {
        background: #ffffff;
        padding: 18px 22px;
        border-radius: 14px;
        box-shadow: 0 2px 12px rgba(0,0,0,0.07);
        margin-bottom: 18px;
        border-right: 6px solid #2a9d8f;
        border-left: 1px solid #e8edf2;
        border-top: 1px solid #e8edf2;
        border-bottom: 1px solid #e8edf2;
        direction: rtl !important;
        transition: all 0.3s ease;
    }
    
    .offer-card:hover {
        box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        transform: translateY(-1px);
    }
    
    .sub-card {
        background: #f7f9fc;
        padding: 18px 20px;
        border-radius: 10px;
        border: 1px dashed #00b4d8;
        margin-top: 12px;
    }
    
    /* ---------- القائمة الجانبية ---------- */
    [data-testid="stSidebar"] {
        background-color: #0f1c2e !important;
        padding: 20px 12px !important;
        min-width: 300px !important;
    }
    
    [data-testid="stSidebar"] * {
        color: #ffffff !important;
    }
    
    [data-testid="stSidebar"] .stRadio label {
        color: #ffffff !important;
        font-size: 16px !important;
        font-weight: 500 !important;
    }
    
    [data-testid="stSidebar"] .stRadio label:hover {
        color: #00b4d8 !important;
    }
    
    [data-testid="stSidebar"] h2 {
        color: #00b4d8 !important;
        font-size: 24px !important;
        font-weight: 700 !important;
        text-align: center !important;
        padding-bottom: 12px;
        border-bottom: 2px solid rgba(0, 180, 216, 0.25);
    }
    
    /* ---------- زر التحديث ---------- */
    .refresh-btn-container {
        margin-top: 10px;
    }
    
    .refresh-btn-container button {
        background: linear-gradient(135deg, #dc3545, #c82333) !important;
        color: #ffffff !important;
        font-weight: 700 !important;
        font-size: 17px !important;
        border-radius: 10px !important;
        height: 48px !important;
        border: none !important;
        box-shadow: 0 4px 15px rgba(220, 53, 69, 0.35) !important;
        transition: all 0.3s ease !important;
    }
    
    .refresh-btn-container button:hover {
        transform: scale(1.03) !important;
        box-shadow: 0 6px 25px rgba(220, 53, 69, 0.5) !important;
    }
    
    /* ---------- الأزرار العامة ---------- */
    .stButton>button {
        width: 100% !important;
        font-weight: 700 !important;
        border-radius: 8px !important;
        height: 44px !important;
        border: none !important;
        transition: all 0.3s ease !important;
    }
    
    .stButton>button:hover {
        transform: scale(1.02) !important;
        box-shadow: 0 4px 15px rgba(0,0,0,0.12) !important;
    }
    
    /* أزرار صغيرة للتحكم السريع */
    .small-btn button {
        height: 32px !important;
        font-size: 12px !important;
        padding: 0 12px !important;
        min-width: 70px !important;
    }
    
    /* ---------- روابط المنتجات ---------- */
    .product-link {
        color: #00b4d8 !important;
        font-weight: 700;
        text-decoration: none;
        font-size: 18px;
        transition: all 0.3s ease;
    }
    
    .product-link:hover {
        color: #0077b6 !important;
        text-decoration: underline !important;
    }
    
    /* ---------- شارات الحالة ---------- */
    .badge-success {
        background: #d4edda;
        color: #155724;
        padding: 3px 12px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 12px;
        display: inline-block;
    }
    
    .badge-danger {
        background: #f8d7da;
        color: #721c24;
        padding: 3px 12px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 12px;
        display: inline-block;
    }
    
    .badge-warning {
        background: #fff3cd;
        color: #856404;
        padding: 3px 12px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 12px;
        display: inline-block;
    }
    
    /* ---------- التذييل ---------- */
    .footer {
        text-align: center;
        padding: 20px;
        color: #6c757d;
        border-top: 1px solid #e9ecef;
        margin-top: 35px;
        font-size: 13px;
    }
    
    /* ---------- عرض العروض ---------- */
    .offers-count {
        background: #f0f4f8;
        padding: 10px 18px;
        border-radius: 10px;
        margin-bottom: 18px;
        border-right: 4px solid #00b4d8;
    }
    
    .offer-date {
        color: #6c757d;
        font-size: 13px;
    }
    
    /* ---------- تنسيق الإشعارات ---------- */
    .stAlert {
        border-radius: 10px !important;
        direction: rtl !important;
    }
    
    /* ---------- حقول الإدخال ---------- */
    .stTextInput>div>div>input,
    .stNumberInput>div>div>input {
        border-radius: 8px !important;
        border: 2px solid #e2e8f0 !important;
        transition: all 0.3s ease !important;
        background: #ffffff !important;
    }
    
    .stTextInput>div>div>input:focus,
    .stNumberInput>div>div>input:focus {
        border-color: #00b4d8 !important;
        box-shadow: 0 0 0 3px rgba(0, 180, 216, 0.15) !important;
    }
    
    .stSelectbox>div>div {
        border-radius: 8px !important;
        border: 2px solid #e2e8f0 !important;
        background: #ffffff !important;
    }
    
    /* ---------- تحسين الصفوف في البطاقات ---------- */
    .product-info {
        font-size: 14px;
        line-height: 1.8;
    }
    
    .product-detail-row {
        display: flex;
        align-items: center;
        gap: 8px;
        flex-wrap: wrap;
        margin-bottom: 4px;
    }
    
    .product-detail-row .label {
        font-weight: 600;
        color: #4a5568;
        min-width: 80px;
    }
    
    .product-detail-row .value {
        color: #2d3748;
    }
    
    /* تحسين عرض الأزرار الصغيرة */
    .action-buttons {
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
        align-items: center;
    }
    
    .action-buttons .stButton {
        flex: 0 0 auto;
        width: auto !important;
    }
    
    .action-buttons .stButton button {
        width: auto !important;
        padding: 0 16px !important;
        height: 34px !important;
        font-size: 13px !important;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# دوال مساعدة
# ==========================================

def safe_parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """تحليل آمن للتاريخ"""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
    except (ValueError, TypeError):
        try:
            return datetime.strptime(date_str, '%Y-%m-%d')
        except (ValueError, TypeError):
            return None

def parse_products_cleanly(product_list: Optional[List]) -> str:
    """تحليل المنتجات"""
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
    """استخراج سعر المنتج"""
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
        error_msg = str(e)
        if hasattr(e, 'response') and e.response:
            try:
                error_data = e.response.json()
                error_msg = error_data.get('error', {}).get('message', str(e))
            except:
                pass
        st.error(f"⚠️ خطأ: {error_msg}")
        logger.error(f"API Error: {e}")
        return None
    except json.JSONDecodeError as e:
        st.error(f"⚠️ خطأ في تحليل البيانات: {str(e)}")
        return None

def get_headers():
    return {
        "Authorization": f"Bearer {st.session_state.get('access_token', '')}",
        "Content-Type": "application/json"
    }

# ==========================================
# دالة معالجة استيراد الإكسيل
# ==========================================

def process_excel_import(df: pd.DataFrame) -> Dict:
    """معالجة ملف الإكسيل واستيراد العروض"""
    results = {
        "success": [],
        "errors": []
    }
    
    headers = get_headers()
    
    for idx, row in df.iterrows():
        try:
            action = str(row.get('Action', 'create')).strip().lower()
            offer_id = row.get('Offer_ID')
            
            # بناء بيانات العرض
            offer_data = {
                "name": str(row.get('Offer_Name', 'عرض جديد')),
                "offer_type": str(row.get('Offer_Type', 'buy_x_get_y')),
                "applied_channel": str(row.get('Applied_Channel', 'browser_and_application')),
                "start_date": str(row.get('Start_Date_Time', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))),
                "expiry_date": str(row.get('Expiry_Date_Time', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))),
                "message": str(row.get('Offer_Message', ''))
            }
            
            # إضافة بيانات الشراء
            buy_type = str(row.get('Buy_Type', 'product'))
            buy_qty = int(row.get('Buy_Quantity', 1)) if pd.notna(row.get('Buy_Quantity')) else 1
            buy_products = str(row.get('Buy_Products_IDs', '')).split(',') if pd.notna(row.get('Buy_Products_IDs')) else []
            buy_products = [int(p.strip()) for p in buy_products if p.strip().isdigit()]
            
            offer_data["buy"] = {
                "type": buy_type,
                "quantity": buy_qty
            }
            if buy_products:
                offer_data["buy"]["products"] = buy_products
            
            # إضافة بيانات الهدية
            get_type = str(row.get('Get_Type', 'product'))
            get_qty = int(row.get('Get_Quantity', 1)) if pd.notna(row.get('Get_Quantity')) else 1
            discount_type = str(row.get('Discount_Type', 'percentage'))
            discount_amount = float(row.get('Discount_Amount', 0)) if pd.notna(row.get('Discount_Amount')) else 0
            get_products = str(row.get('Get_Products_IDs', '')).split(',') if pd.notna(row.get('Get_Products_IDs')) else []
            get_products = [int(p.strip()) for p in get_products if p.strip().isdigit()]
            
            offer_data["get"] = {
                "type": get_type,
                "quantity": get_qty,
                "discount_type": discount_type
            }
            if discount_amount > 0:
                offer_data["get"]["discount_amount"] = discount_amount
            if get_products:
                offer_data["get"]["products"] = get_products
            
            # تنفيذ الإجراء
            if action in ['create', 'update']:
                if action == 'create':
                    response = safe_api_request("POST", "https://api.salla.dev/admin/v2/specialoffers", headers, json=offer_data)
                    if response:
                        results["success"].append(f"✅ تم إنشاء العرض: {offer_data['name']}")
                    else:
                        results["errors"].append(f"❌ فشل إنشاء العرض: {offer_data['name']}")
                elif action == 'update' and offer_id:
                    response = safe_api_request("PUT", f"https://api.salla.dev/admin/v2/specialoffers/{offer_id}", headers, json=offer_data)
                    if response:
                        results["success"].append(f"✅ تم تحديث العرض ID: {offer_id}")
                    else:
                        results["errors"].append(f"❌ فشل تحديث العرض ID: {offer_id}")
            
            elif action == 'delete' and offer_id:
                response = safe_api_request("DELETE", f"https://api.salla.dev/admin/v2/specialoffers/{offer_id}", headers)
                if response:
                    results["success"].append(f"✅ تم حذف العرض ID: {offer_id}")
                else:
                    results["errors"].append(f"❌ فشل حذف العرض ID: {offer_id}")
            
            elif action in ['active', 'inactive'] and offer_id:
                status = "active" if action == 'active' else "inactive"
                response = safe_api_request("PUT", f"https://api.salla.dev/admin/v2/specialoffers/{offer_id}/status", headers, json={"status": status})
                if response:
                    results["success"].append(f"✅ تم تغيير حالة العرض ID: {offer_id} إلى {status}")
                else:
                    results["errors"].append(f"❌ فشل تغيير حالة العرض ID: {offer_id}")
            
            else:
                results["errors"].append(f"⚠️ إجراء غير معروف: {action} لـ {offer_id}")
                
        except Exception as e:
            results["errors"].append(f"❌ خطأ في الصف {idx+1}: {str(e)}")
            logger.error(f"Import error: {traceback.format_exc()}")
    
    return results

# ==========================================
# دالة إنشاء نموذج الإكسيل
# ==========================================

def generate_salla_excel_template() -> bytes:
    """إنشاء نموذج Excel احترافي"""
    try:
        try:
            from openpyxl.styles import PatternFill, Font, Alignment
            from openpyxl.worksheet.datavalidation import DataValidation
            from openpyxl import Workbook
        except ImportError:
            import subprocess
            subprocess.check_call(["pip", "install", "openpyxl"])
            from openpyxl.styles import PatternFill, Font, Alignment
            from openpyxl.worksheet.datavalidation import DataValidation
            from openpyxl import Workbook
        
        output = io.BytesIO()
        
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
        
        wb = Workbook()
        ws = wb.active
        ws.title = "قائمة العروض"
        
        # إضافة الرؤوس
        for col_idx, col_name in enumerate(columns, 1):
            cell = ws.cell(row=2, column=col_idx, value=col_name)
        
        # إضافة البيانات
        for row_idx, row_data in enumerate(sample_data, 3):
            for col_idx, value in enumerate(row_data, 1):
                ws.cell(row=row_idx, column=col_idx, value=value)
        
        # تنسيق الرؤوس
        header_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
        header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
        header_alignment = Alignment(horizontal="center", vertical="center")
        
        for col_idx in range(1, len(columns) + 1):
            cell = ws.cell(row=2, column=col_idx)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = header_alignment
        
        # ضبط عرض الأعمدة
        for col in ws.columns:
            max_length = 0
            column = col[0].column_letter
            for cell in col:
                try:
                    val = str(cell.value or '')
                    if len(val) > max_length:
                        max_length = len(val)
                except:
                    pass
            adjusted_width = min(max_length + 2, 30)
            ws.column_dimensions[column].width = adjusted_width
        
        # --- إضافة القوائم المنسدلة ---
        dv_action = DataValidation(
            type="list",
            formula1='"create,update,active,inactive,delete"',
            allow_blank=True,
            showErrorMessage=True,
            errorTitle="قيمة غير صحيحة",
            error="الرجاء اختيار أحد الإجراءات المتاحة"
        )
        ws.add_data_validation(dv_action)
        dv_action.add("A3:A100")
        
        dv_offer_type = DataValidation(
            type="list",
            formula1='"buy_x_get_y,percentage,fixed_amount,discounts_table,tiered_offer,cart_offer,special_price"',
            allow_blank=True,
            showErrorMessage=True,
            errorTitle="نوع عرض غير صحيح",
            error="الرجاء اختيار نوع العرض المناسب"
        )
        ws.add_data_validation(dv_offer_type)
        dv_offer_type.add("D3:D100")
        
        dv_channel = DataValidation(
            type="list",
            formula1='"browser,browser_and_application"',
            allow_blank=True,
            showErrorMessage=True,
            errorTitle="قناة غير صحيحة",
            error="الرجاء اختيار القناة المناسبة"
        )
        ws.add_data_validation(dv_channel)
        dv_channel.add("E3:E100")
        
        dv_coupon = DataValidation(
            type="list",
            formula1='"نعم,لا"',
            allow_blank=True,
            showErrorMessage=True,
            errorTitle="قيمة غير صحيحة",
            error="الرجاء اختيار نعم أو لا"
        )
        ws.add_data_validation(dv_coupon)
        dv_coupon.add("F3:F100")
        
        dv_disc_type = DataValidation(
            type="list",
            formula1='"percentage,free-product"',
            allow_blank=True,
            showErrorMessage=True,
            errorTitle="نوع خصم غير صحيح",
            error="الرجاء اختيار نوع الخصم المناسب"
        )
        ws.add_data_validation(dv_disc_type)
        dv_disc_type.add("N3:N100")
        
        # تنسيق خانات التاريخ
        from openpyxl.styles import numbers
        for row in range(3, 100):
            for col in ['G', 'H']:  # عمودي التاريخ
                cell = ws[f"{col}{row}"]
                cell.number_format = numbers.FORMAT_DATE_DATETIME
        
        # إضافة تعليمات
        ws.insert_rows(1)
        ws.merge_cells('A1:Q1')
        instructions_cell = ws.cell(row=1, column=1)
        instructions_cell.value = "📋 تعليمات التعبئة: استخدم Action=create للإضافة، update للتحديث، delete للحذف، active/inactive لتغيير الحالة"
        instructions_cell.font = Font(name="Segoe UI", size=12, bold=True, color="1F497D")
        instructions_cell.alignment = Alignment(horizontal="center", vertical="center")
        
        wb.save(output)
        output.seek(0)
        return output.getvalue()
        
    except Exception as e:
        logger.error(f"Error generating template: {e}")
        st.error(f"⚠️ خطأ في إنشاء النموذج: {str(e)}")
        
        # إنشاء ملف بديل
        columns = [
            "Action", "Offer_ID", "Offer_Name", "Offer_Type", "Applied_Channel",
            "With_Coupon", "Start_Date_Time", "Expiry_Date_Time", "Buy_Type",
            "Buy_Quantity", "Buy_Products_IDs", "Get_Type", "Get_Quantity",
            "Discount_Type", "Discount_Amount", "Get_Products_IDs", "Offer_Message"
        ]
        df = pd.DataFrame(columns=columns)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='قائمة العروض')
        buffer.seek(0)
        return buffer.getvalue()

# ==========================================
# إدارة جلسة الدخول
# ==========================================

def init_session_state():
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

# ==========================================
# شاشة الدخول
# ==========================================

if not st.session_state["logged_in"]:
    st.markdown("<div class='login-container'>", unsafe_allow_html=True)
    st.markdown("""
        <div style="text-align: center; margin-bottom: 25px;">
            <h1 style="color: #0f1c2e; font-weight: 700; font-size: 26px;">🛡️ منظومة بلسم</h1>
            <p style="color: #6c757d; font-size: 15px;">تسجيل الدخول الآمن إلى لوحة التحكم</p>
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
                st.error("❌ بيانات الدخول خاطئة.")
    
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# ==========================================
# إعدادات API
# ==========================================

SALLA_API_URL = "https://api.salla.dev/admin/v2/specialoffers"

# ==========================================
# الشريط العلوي
# ==========================================

st.markdown(f"""
    <div class='top-sticky-bar'>
        <div class='title'>🛡️ لوحة التحكم الإدارية لصيدليات بلسم العُلا</div>
        <div class='status'>✅ الاتصال موثق ومستقر</div>
    </div>
""", unsafe_allow_html=True)

# ==========================================
# أزرار التحكم العلوية
# ==========================================

top_c1, top_col2, _ = st.columns([1.5, 1.5, 4])
with top_c1:
    with st.popover("🔑 تعديل مفتاح الربط"):
        new_tok = st.text_input("أدخل التوكن الجديد:", value=st.session_state["access_token"], type="password")
        if st.button("تحديث التوكن", use_container_width=True):
            if new_tok.strip():
                st.session_state["access_token"] = new_tok.strip()
                st.success("✅ تم تحديث التوكن!")
                st.rerun()
            else:
                st.warning("⚠️ الرجاء إدخال توكن صحيح")

with top_col2:
    with st.popover("🔒 تعديل كلمة المرور"):
        new_pwd = st.text_input("أدخل كلمة المرور الجديدة:", type="password")
        if st.button("تحديث الباسورد", use_container_width=True):
            if new_pwd.strip():
                st.session_state["admin_password"] = new_pwd.strip()
                st.success("✅ تم تحديث كلمة المرور!")
            else:
                st.warning("⚠️ الرجاء إدخال كلمة مرور صحيحة")

st.divider()

# ==========================================
# القائمة الجانبية
# ==========================================

st.sidebar.markdown("""
    <div style="text-align: center; padding: 10px 0;">
        <h2>🏥 بوابة بلسم الرقمية</h2>
        <p style="color: #8c9aa8; font-size: 13px; margin-top: 5px;">منظومة إدارة العروض والمنتجات</p>
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

st.sidebar.markdown("<div class='refresh-btn-container'>", unsafe_allow_html=True)
if st.sidebar.button("🔄 تحديث البيانات والصفحة", key="refresh_page_btn", use_container_width=True):
    st.rerun()
st.sidebar.markdown("</div>", unsafe_allow_html=True)

with st.sidebar.expander("ℹ️ معلومات النظام", expanded=False):
    st.caption(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    st.caption("🔗 https://api.salla.dev/admin/v2")
    st.caption("📊 الحالة: متصل")

# ==========================================
# الشاشة الأولى: لوحة العروض
# ==========================================

if page == "📊 لوحة تصفية وإدارة العروض الحالية":
    st.markdown("""
        <h1 style='color: #0f1c2e; font-weight: 700; margin-bottom: 8px; font-size: 28px;'>
            📊 لوحة إدارة العروض الاحترافية
        </h1>
        <p style='color: #6c757d; margin-bottom: 25px; font-size: 15px;'>
            إدارة شاملة للعروض مع إمكانية التصفية والبحث والتعديل الفوري
        </p>
    """, unsafe_allow_html=True)
    
    # نموذج الاستيراد
    col_info, col_btn = st.columns([3, 1])
    with col_info:
        st.info("📥 قم بتنزيل النموذج الاحترافي وتعبئة البيانات بالصيغ المحددة")
    with col_btn:
        st.download_button(
            label="📥 تحميل النموذج",
            data=generate_salla_excel_template(),
            file_name="Salla_Offers_Template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    
    uploaded_file = st.file_uploader(
        "📂 اختر ملف العروض بصيغة XLSX للاستيراد الجماعي:",
        type=["xlsx"],
        help="قم بتحميل ملف الإكسيل المعبأ وفق النموذج"
    )
    
    if uploaded_file:
        try:
            df_user = pd.read_excel(uploaded_file)
            st.success(f"✅ تم تحميل الملف! يحتوي على {len(df_user)} عرض")
            st.dataframe(df_user, use_container_width=True)
            
            if st.button("🚀 تأكيد النشر الجماعي", use_container_width=True, type="primary"):
                with st.spinner("🔄 جاري معالجة العروض..."):
                    results = process_excel_import(df_user)
                
                # عرض النتائج
                if results["success"]:
                    for msg in results["success"]:
                        st.success(msg)
                if results["errors"]:
                    for msg in results["errors"]:
                        st.error(msg)
                
                if results["success"]:
                    st.balloons()
                    st.rerun()
                    
        except Exception as e:
            st.error(f"⚠️ خطأ في قراءة الملف: {str(e)}")
    
    st.divider()
    
    # جلب العروض
    with st.spinner("🔄 جاري تحميل العروض..."):
        res = safe_api_request("GET", SALLA_API_URL, get_headers())
    
    if res and res.get("data"):
        raw_offers = res["data"]
        
        # فلترة العروض
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
                    ["الكل", "buy_x_get_y", "percentage", "fixed_amount", "discounts_table", "tiered_offer", "cart_offer", "special_price"]
                )
        
        # تصفية العروض
        now = datetime.now()
        filtered_offers = []
        
        for offer in raw_offers:
            match = True
            start_date = safe_parse_date(offer.get('start_date'))
            expiry_date = safe_parse_date(offer.get('expiry_date'))
            
            if search_offer:
                search_lower = search_offer.lower()
                offer_name = offer.get('name', '').lower()
                offer_id = str(offer.get('id', ''))
                
                buy_products = offer.get('buy', {}).get('products', [])
                get_products = offer.get('get', {}).get('products', [])
                all_ids = []
                for p in buy_products + get_products:
                    if isinstance(p, dict):
                        all_ids.append(str(p.get('id', '')))
                        all_ids.append(str(p.get('sku', '')).lower())
                    else:
                        all_ids.append(str(p))
                
                if search_lower not in offer_name and search_lower not in offer_id:
                    if not any(search_lower in pid for pid in all_ids):
                        match = False
            
            if offer_type_filter != "الكل" and offer.get('offer_type') != offer_type_filter:
                match = False
            
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
        
        st.markdown(f"""
            <div class='offers-count'>
                <strong>📊 عدد العروض: {len(filtered_offers)} عرض</strong>
            </div>
        """, unsafe_allow_html=True)
        
        # عرض العروض
        for idx, offer in enumerate(filtered_offers):
            with st.container():
                st.markdown(f"<div class='offer-card'>", unsafe_allow_html=True)
                
                col1, col2, col3, col4 = st.columns([3, 1.2, 1.2, 1.2])
                
                with col1:
                    offer_name = offer.get('name', 'عرض بدون اسم')
                    offer_id = offer.get('id', 'N/A')
                    start = offer.get('start_date', 'غير محدد')
                    expiry = offer.get('expiry_date', 'غير محدد')
                    
                    st.markdown(f"""
                        <div>
                            <h4 style="margin: 0 0 5px 0; color: #0f1c2e; font-size: 18px;">🎯 {offer_name}</h4>
                            <span style="color: #6c757d; font-size: 13px;">🆔 ID: {offer_id}</span>
                            <br>
                            <span class="offer-date">📅 {start} → {expiry}</span>
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
                    if st.button(btn_label, key=f"toggle_status_{offer_id}_{idx}", use_container_width=True):
                        with st.spinner("🔄 جاري تحديث الحالة..."):
                            update_res = safe_api_request(
                                "PUT",
                                f"{SALLA_API_URL}/{offer_id}/status",
                                get_headers(),
                                json={"status": target_status}
                            )
                            if update_res:
                                st.success("✅ تم تحديث الحالة!")
                                st.rerun()
                
                with col4:
                    if st.button("🗑️ حذف", key=f"delete_offer_{offer_id}_{idx}", use_container_width=True, type="primary"):
                        with st.spinner("🔄 جاري الحذف..."):
                            del_res = safe_api_request("DELETE", f"{SALLA_API_URL}/{offer_id}", get_headers())
                            if del_res is not None:
                                st.success("✅ تم حذف العرض!")
                                st.rerun()
                
                # تفاصيل العرض
                with st.expander("🔽 تفاصيل العرض المتقدمة", expanded=False):
                    st.markdown("<div class='sub-card'>", unsafe_allow_html=True)
                    
                    col_left, col_right = st.columns(2)
                    
                    with col_left:
                        st.markdown("**🛒 منتجات الشراء (X):**")
                        buy_products = offer.get('buy', {}).get('products', [])
                        st.text(parse_products_cleanly(buy_products))
                        buy_qty = offer.get('buy', {}).get('quantity', 1)
                        st.markdown(f"**📦 كمية الشراء:** `{buy_qty}`")
                    
                    with col_right:
                        st.markdown("**🎁 منتجات الهدية (Y):**")
                        get_products = offer.get('get', {}).get('products', [])
                        st.text(parse_products_cleanly(get_products))
                        get_qty = offer.get('get', {}).get('quantity', 1)
                        st.markdown(f"**🎯 كمية الهدية:** `{get_qty}`")
                    
                    st.divider()
                    
                    # نموذج التعديل
                    st.markdown("#### ✏️ تعديل تفاصيل العرض")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        ed_name = st.text_input("اسم العرض:", value=offer.get('name', ''), key=f"edit_name_{offer_id}")
                        ed_msg = st.text_input("الرسالة الترويجية:", value=offer.get('message', ''), key=f"edit_msg_{offer_id}")
                    
                    with col2:
                        offer_types = ["buy_x_get_y", "percentage", "fixed_amount", "discounts_table", "tiered_offer", "cart_offer", "special_price"]
                        current_type = offer.get('offer_type', 'buy_x_get_y')
                        type_index = offer_types.index(current_type) if current_type in offer_types else 0
                        ed_type = st.selectbox(
                            "نوع العرض:",
                            offer_types,
                            index=type_index,
                            key=f"edit_type_{offer_id}"
                        )
                    
                    # خانات التاريخ مع مساعد
                    st.markdown("**📅 التواريخ:**")
                    col1, col2 = st.columns(2)
                    with col1:
                        ed_start = st.text_input(
                            "تاريخ البدء:",
                            value=offer.get('start_date', ''),
                            key=f"edit_start_{offer_id}",
                            help="صيغة: YYYY-MM-DD HH:mm:ss"
                        )
                    with col2:
                        ed_end = st.text_input(
                            "تاريخ الانتهاء:",
                            value=offer.get('expiry_date', ''),
                            key=f"edit_end_{offer_id}",
                            help="صيغة: YYYY-MM-DD HH:mm:ss"
                        )
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        buy_qty_val = int(offer.get('buy', {}).get('quantity', 1))
                        ed_buy_q = st.number_input(
                            "كمية الشراء المطلوبة:",
                            value=buy_qty_val,
                            min_value=1,
                            key=f"edit_buy_q_{offer_id}"
                        )
                    with col2:
                        get_qty_val = int(offer.get('get', {}).get('quantity', 1))
                        ed_get_q = st.number_input(
                            "كمية الهدية:",
                            value=get_qty_val,
                            min_value=1,
                            key=f"edit_get_q_{offer_id}"
                        )
                    
                    if st.button("💾 حفظ التحديثات", key=f"save_offer_{offer_id}", use_container_width=True, type="primary"):
                        try:
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
                            
                            # إضافة المنتجات إذا كانت موجودة
                            buy_products_ids = []
                            for p in offer.get('buy', {}).get('products', []):
                                if isinstance(p, dict):
                                    buy_products_ids.append(p.get('id'))
                                else:
                                    buy_products_ids.append(p)
                            if buy_products_ids:
                                update_payload["buy"]["products"] = buy_products_ids
                            
                            get_products_ids = []
                            for p in offer.get('get', {}).get('products', []):
                                if isinstance(p, dict):
                                    get_products_ids.append(p.get('id'))
                                else:
                                    get_products_ids.append(p)
                            if get_products_ids:
                                update_payload["get"]["products"] = get_products_ids
                            
                            with st.spinner("🔄 جاري حفظ التغييرات..."):
                                update_res = safe_api_request(
                                    "PUT",
                                    f"{SALLA_API_URL}/{offer_id}",
                                    get_headers(),
                                    json=update_payload
                                )
                                if update_res:
                                    st.success("✅ تم تحديث العرض!")
                                    st.rerun()
                        except Exception as e:
                            st.error(f"❌ خطأ: {str(e)}")
                    
                    st.markdown("</div>", unsafe_allow_html=True)
                
                st.markdown("</div>", unsafe_allow_html=True)
    
    else:
        st.warning("⚠️ لا توجد عروض حالياً في المتجر")

# ==========================================
# الشاشة الثانية: مركز جرد المنتجات
# ==========================================

elif page == "📦 مركز جرد المنتجات ومعرفات الـ IDs":
    st.markdown("""
        <h1 style='color: #0f1c2e; font-weight: 700; margin-bottom: 8px; font-size: 28px;'>
            📦 مركز جرد المنتجات
        </h1>
        <p style='color: #6c757d; margin-bottom: 25px; font-size: 15px;'>
            إدارة المنتجات وحالة الظهور وعرض العروض المرتبطة
        </p>
    """, unsafe_allow_html=True)
    
    with st.spinner("🔄 جاري تحميل المنتجات والعروض..."):
        products_res = safe_api_request("GET", "https://api.salla.dev/admin/v2/products", get_headers())
        offers_res = safe_api_request("GET", SALLA_API_URL, get_headers())
    
    if products_res and products_res.get("data") and offers_res:
        products = products_res["data"]
        offers = offers_res.get("data", [])
        
        st.info(f"📊 عدد المنتجات: {len(products)} منتج")
        
        # إنشاء قاموس للعروض المرتبطة
        offer_map = {}
        for offer in offers:
            buy_products = offer.get('buy', {}).get('products', [])
            get_products = offer.get('get', {}).get('products', [])
            for p in buy_products + get_products:
                if isinstance(p, dict):
                    product_id = p.get('id')
                    if product_id:
                        offer_map[product_id] = offer
                else:
                    offer_map[p] = offer
        
        # البحث عن المنتجات
        search_query = st.text_input(
            "🔍 ابحث هنا بواسطة اسم المنتج أو الـ SKU:",
            placeholder="أدخل اسم المنتج أو SKU...",
            help="ابحث عن منتج معين لعرض تفاصيله وإدارته"
        )
        
        # تصفية المنتجات
        filtered_products = []
        if search_query:
            search_lower = search_query.lower()
            for p in products:
                if (search_lower in p.get('name', '').lower() or 
                    search_lower in str(p.get('sku', '')).lower() or
                    search_lower in str(p.get('id', ''))):
                    filtered_products.append(p)
        else:
            filtered_products = products[:20]
            if len(products) > 20:
                st.info("📌 عرض أول 20 منتج. استخدم البحث لعرض المزيد.")
        
        if not filtered_products:
            st.warning("⚠️ لم يتم العثور على منتجات تطابق البحث")
        
        # عرض المنتجات
        for idx, p in enumerate(filtered_products):
            p_id = p.get('id', 'N/A')
            p_name = p.get('name', 'منتج بدون اسم')
            p_sku = p.get('sku', 'لا يوجد')
            p_promotion = p.get('promotion_title', '')
            
            # التحقق من وجود عرض
            offer = offer_map.get(p_id)
            has_offer = offer is not None
            
            # تصميم البطاقة المحسن
            st.markdown(f"""
                <div class='product-card'>
                    <div class='product-card-header'>
                        <span class='product-name'>📦 {p_name}</span>
                        <span class='product-promotion'>🏷️ {p_promotion if p_promotion else 'لا يوجد عنوان ترويجي'}</span>
                    </div>
                    <div class='product-card-body'>
            """, unsafe_allow_html=True)
            
            col1, col2, col3, col4 = st.columns([2.5, 2, 1.8, 2])
            
            with col1:
                product_url = p.get('url', '#')
                st.markdown(f"<a href='{product_url}' target='_blank' class='product-link'>{p_name}</a>", unsafe_allow_html=True)
                st.caption(f"🏷️ SKU: `{p_sku}`")
                st.caption(f"🆔 ID: `{p_id}`")
                
                if p.get('thumbnail') or p.get('main_image'):
                    st.markdown("<span style='color: #2a9d8f;'>✅ يحتوي على صورة</span>", unsafe_allow_html=True)
                else:
                    st.markdown("<span style='color: #e76f51;'>⚠️ يحتاج لصورة</span>", unsafe_allow_html=True)
            
            with col2:
                price = get_product_price(p)
                st.markdown(f"**💰 السعر:** {price:,.2f} SAR")
                st.markdown(f"**📦 المخزون:** {p.get('quantity', 0)} حبة")
                st.markdown(f"**📈 المبيعات:** {p.get('sold_quantity', 0)}")
                
                status = p.get('status', 'sale')
                status_text = "🟢 معروض" if status == "sale" else "🔴 مخفي"
                st.markdown(f"**👁️ الحالة:** {status_text}")
            
            with col3:
                if has_offer:
                    offer_status = offer.get('status', '')
                    offer_id = offer.get('id', '')
                    status_color = "🟢" if offer_status == "active" else "🔴"
                    status_text = "نشط" if offer_status == "active" else "غير نشط"
                    
                    st.markdown(f"""
                        <div style="border: 1px solid #e8edf2; border-radius: 8px; padding: 10px; background: #f8f9fa;">
                            <strong>🎯 عرض:</strong> {offer.get('name', 'عرض')}
                            <br>
                            <span style="font-size: 12px;">🆔 {offer_id}</span>
                            <br>
                            <span style="font-size: 12px;">{status_color} {status_text}</span>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    # أزرار التحكم الصغيرة
                    st.markdown("<div class='action-buttons'>", unsafe_allow_html=True)
                    
                    # زر إيقاف/تفعيل العرض
                    if offer_status == "active":
                        if st.button("⏸️ إيقاف العرض", key=f"pause_offer_{p_id}_{idx}", use_container_width=True):
                            with st.spinner("🔄 جاري إيقاف العرض..."):
                                update_res = safe_api_request(
                                    "PUT",
                                    f"{SALLA_API_URL}/{offer_id}/status",
                                    get_headers(),
                                    json={"status": "inactive"}
                                )
                                if update_res:
                                    st.success("✅ تم إيقاف العرض!")
                                    st.rerun()
                    else:
                        if st.button("▶️ تفعيل العرض", key=f"activate_offer_{p_id}_{idx}", use_container_width=True):
                            with st.spinner("🔄 جاري تفعيل العرض..."):
                                update_res = safe_api_request(
                                    "PUT",
                                    f"{SALLA_API_URL}/{offer_id}/status",
                                    get_headers(),
                                    json={"status": "active"}
                                )
                                if update_res:
                                    st.success("✅ تم تفعيل العرض!")
                                    st.rerun()
                    
                    st.markdown("</div>", unsafe_allow_html=True)
                    
                else:
                    st.markdown("**⚪ لا يوجد عرض**")
                    st.button("إضافة عرض", key=f"add_offer_{p_id}_{idx}", disabled=True, use_container_width=True)
            
            with col4:
                # زر نسخ المعرف
                if st.button("📋 نسخ ID", key=f"copy_id_{p_id}_{idx}", use_container_width=True):
                    st.toast(f"✅ تم نسخ المعرف: {p_id}")
                
                # زر تغيير حالة الظهور (المُصحح)
                current_status = p.get('status', 'sale')
                btn_label = "👁️ إخفاء" if current_status == "sale" else "👁️ إظهار"
                btn_type = "primary" if current_status == "sale" else "secondary"
                
                if st.button(btn_label, key=f"toggle_status_{p_id}_{idx}", use_container_width=True, type=btn_type):
                    target_status = "hidden" if current_status == "sale" else "sale"
                    
                    with st.spinner("🔄 جاري تحديث الحالة..."):
                        # استخدام PUT مع تحديث المنتج مباشرة بدلاً من تغيير الحالة
                        update_payload = {"status": target_status}
                        update_res = safe_api_request(
                            "PUT",
                            f"https://api.salla.dev/admin/v2/products/{p_id}",
                            get_headers(),
                            json=update_payload
                        )
                        if update_res is not None:
                            st.success("✅ تم تحديث حالة المنتج!")
                            st.rerun()
            
            st.markdown("</div></div>", unsafe_allow_html=True)
    
    else:
        st.error("⚠️ فشل في تحميل البيانات. يرجى التحقق من الاتصال والتوكن.")

# ==========================================
# التذييل
# ==========================================

st.markdown("""
    <div class='footer'>
        <p>© 2026 منظومة بلسم الرقمية | جميع الحقوق محفوظة</p>
        <p style='font-size: 11px; color: #adb5bd;'>تم التطوير باستخدام Streamlit</p>
    </div>
""", unsafe_allow_html=True)
