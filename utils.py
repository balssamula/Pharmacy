import streamlit as st
import pandas as pd
import io
import requests
import json
import logging
import re
from datetime import datetime
from typing import Optional, List, Dict, Any
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.utils import get_column_letter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SALLA_API_URL = "https://api.salla.dev/admin/v2/specialoffers"

def safe_parse_date(date_str: Optional[str]) -> Optional[datetime]:
    if not date_str: return None
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%a %b %d %Y %H:%M:%S'):
        try:
            clean_str = re.sub(r' GMT.*$', '', str(date_str))
            return datetime.strptime(clean_str, fmt)
        except (ValueError, TypeError): pass
    return None

def parse_products_cleanly(offer_section: Dict) -> str:
    if not offer_section or not isinstance(offer_section, dict):
        return "كل منتجات المتجر"
    clean_elements = []
    
    products = offer_section.get('products', [])
    if products and isinstance(products, list):
        for p in products:
            if isinstance(p, dict):
                name = p.get('name', 'غير معرف')
                p_id = p.get('id', 'N/A')
                sku = p.get('sku', 'لا يوجد SKU')
                clean_elements.append(f"• منتج: {name} [ID: {p_id}] [SKU: {sku}]")
            else:
                clean_elements.append(f"• معرف منتج رقم: {p}")
                
    categories = offer_section.get('categories', [])
    if categories and isinstance(categories, list):
        for c in categories:
            if isinstance(c, dict):
                clean_elements.append(f"• تصنيف: {c.get('name', 'غير معرف')} [ID: {c.get('id', 'N/A')}]")
            else:
                clean_elements.append(f"• معرف تصنيف رقم: {c}")
                
    return "\n".join(clean_elements) if clean_elements else "كل المنتجات المشمولة"

def get_flat_price(price_field: Any) -> float:
    if not price_field: return 0.0
    if isinstance(price_field, dict):
        return float(price_field.get('amount', 0.0))
    try: return float(price_field)
    except (ValueError, TypeError): return 0.0

def safe_api_request(method: str, url: str, headers: Dict, **kwargs) -> Optional[Dict]:
    try:
        response = requests.request(method, url, headers=headers, timeout=30, **kwargs)
        if response.status_code >= 400:
            try: error_detail = json.dumps(response.json(), ensure_ascii=False)
            except: error_detail = response.text[:500]
            if response.status_code != 404:
                st.error(f"⚠️ خطأ {response.status_code}: {error_detail}")
            return None
        return response.json()
    except Exception as e:
        st.error(f"⚠️ خطأ في الاتصال: {str(e)}")
        return None

def get_headers():
    token = st.session_state.get('access_token', '')
    if not token:
        st.warning("⚠️ الرجاء إدخال مفتاح الربط (Access Token)")
        return None
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

def style_excel_file(ws, is_template=False):
    """تطبيق تنسيق احترافي فاخر مع الفلاتر التلقائية للأعمدة"""
    header_fill = PatternFill(start_color="0F1C2E", end_color="1F3A60", fill_type="solid")
    header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
    center_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin_border = Border(
        left=Side(style='thin', color='DDDDDD'), right=Side(style='thin', color='DDDDDD'),
        top=Side(style='thin', color='DDDDDD'), bottom=Side(style='thin', color='DDDDDD')
    )
    
    start_row = 2 if is_template else 1
    ws.row_dimensions[start_row].height = 26
    
    for col in range(1, ws.max_column + 1):
        cell = ws.cell(row=start_row, column=col)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center_alignment
        cell.border = thin_border
        
    last_letter = get_column_letter(ws.max_column)
    ws.auto_filter.ref = f"A{start_row}:{last_letter}{ws.max_row}"
    
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = min(max(max_len + 4, 14), 32)

def export_offers_to_excel(offers: List[Dict]) -> bytes:
    try:
        data = []
        for offer in offers:
            buy_p = [str(p.get('id', p)) if isinstance(p, dict) else str(p) for p in offer.get('buy', {}).get('products', [])]
            get_p = [str(p.get('id', p)) if isinstance(p, dict) else str(p) for p in offer.get('get', {}).get('products', [])]
            data.append({
                'المعرف': offer.get('id', ''), 'اسم العرض': offer.get('name', ''), 'النوع': offer.get('offer_type', ''),
                'الحالة': 'مفعل' if offer.get('status') == 'active' else 'غير مفعل',
                'مع كوبون': 'نعم' if offer.get('applied_with_coupon', False) else 'لا',
                'تاريخ البدء': offer.get('start_date', ''), 'تاريخ الانتهاء': offer.get('expiry_date', ''),
                'منتجات الشراء': ', '.join(buy_p), 'كمية الشراء': offer.get('buy', {}).get('quantity', 1),
                'منتجات الهدية': ', '.join(get_p), 'كمية الهدية': offer.get('get', {}).get('quantity', 1),
                'الرسالة': offer.get('message', '')
            })
        df = pd.DataFrame(data)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
            style_excel_file(writer.sheets['Sheet1'], is_template=False)
        return buffer.getvalue()
    except Exception as e:
        st.error(f"⚠️ خطأ في التصدير: {str(e)}")
        return b""

def export_products_to_excel(products: List[Dict]) -> bytes:
    try:
        data = []
        for p in products:
            price = get_flat_price(p.get('price', 0))
            sale_price = get_flat_price(p.get('sale_price', 0))
            
            promo = p.get('promotion', {})
            promo_title = p.get('promotion_title') or (promo.get('title') if isinstance(promo, dict) else '') or "لا يوجد"
            promo_sub = (promo.get('sub_title') if isinstance(promo, dict) else '') or "لا يوجد"
            
            # جلب تواريخ التخفيض المحددة للصنف
            sale_end_val = p.get('sale_end') or p.get('sale_price', {}).get('expired_at') if isinstance(p.get('sale_price'), dict) else None
            
            data.append({
                'المعرف': p.get('id', ''), 
                'الاسم': p.get('name', ''), 
                'SKU': p.get('sku', ''),
                'السعر الأساسي': price, 
                'السعر المخفض': sale_price if sale_price > 0 else 'لا يوجد',
                'خاضع للضريبة': 'نعم' if p.get('with_tax', True) else 'لا',
                'العنوان الترويجي': promo_title,
                'العنوان الفرعي': promo_sub,
                'تاريخ نهاية التخفيض': sale_end_val if sale_end_val else 'غير محدد',
                'المخزون': p.get('quantity', 0), 
                'المبيعات': p.get('sold_quantity', 0),
                'الحالة': 'معروض' if p.get('status') == 'sale' else 'مخفي'
            })
        df = pd.DataFrame(data)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
            style_excel_file(writer.sheets['Sheet1'], is_template=False)
        return buffer.getvalue()
    except Exception as e:
        st.error(f"⚠️ خطأ في التصدير: {str(e)}")
        return b""

def generate_salla_excel_template() -> bytes:
    from openpyxl import Workbook
    output = io.BytesIO()
    wb = Workbook()
    ws = wb.active
    ws.title = "قائمة العروض"
    
    ws.append(["📋 تعليمات الاستيراد: يرجى استخدام القوائم المنسدلة الظاهرة للاختيار لمنع أي أخطاء في الحقول المرفوعة."])
    ws.merge_cells('A1:S1')
    ws.row_dimensions[1].height = 24
    
    columns = [
        "Action", "Offer_ID", "Offer_Name", "Offer_Type", "Applied_Channel",
        "Applied_To", "With_Coupon", "Offer_Status", "Start_Date_Time", "Expiry_Date_Time", 
        "Buy_Type", "Buy_Quantity", "Buy_Products_IDs", "Get_Type", "Get_Quantity", 
        "Discount_Type", "Discount_Amount", "Get_Products_IDs", "Offer_Message"
    ]
    ws.append(columns)
    ws.append(["create", "", "عرض بلسم الجديد", "buy_x_get_y", "browser_and_application", "product", "لا", "active", "2026-06-23 12:00:00", "2026-07-23 12:00:00", "product", 1, "12345", "product", 1, "free-product", 0, "67890", "خصم خاص"])
    
    style_excel_file(ws, is_template=True)
    
    dv_action = DataValidation(type="list", formula1='"create,update,delete"', allow_blank=True)
    ws.add_data_validation(dv_action)
    dv_action.add("A3:A100")
    
    dv_coupon = DataValidation(type="list", formula1='"نعم,لا"', allow_blank=True)
    ws.add_data_validation(dv_coupon)
    dv_coupon.add("G3:G100")
    
    dv_status = DataValidation(type="list", formula1='"active,inactive"', allow_blank=True)
    ws.add_data_validation(dv_status)
    dv_status.add("H3:H100")
    
    wb.save(output)
    return output.getvalue()

def update_product_status(product_id: int, status: str) -> bool:
    """تحديث حالة الصنف باستخدام الرابط والطلب الصحيح لمنع التداخل وخطأ 422"""
    headers = get_headers()
    if not headers: return False
    
    # استخدام طلب POST الصارم والمباشر المخصص للحالة لمنع تداخل الأسعار
    url = f"https://api.salla.dev/admin/v2/products/{product_id}/status"
    payload = {"status": status}
    
    res = safe_api_request("POST", url, headers, json=payload)
    return res is not None
