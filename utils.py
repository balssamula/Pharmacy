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

# الخرائط الموحدة لترجمة خيارات منصة سلة بالكامل للعربية
OFFER_TYPES_MAP = {
    "buy_x_get_y": "اذا اشترى العميل X يحصل على Y",
    "fixed_amount": "مبلغ ثابت من قيمة مشتريات العميل",
    "percentage": "نسبة من قيمة مشتريات العميل",
    "discounts_table": "جدول الخصومات",
    "special_price": "سعر ثابت",
    "tiered_offer": "عرض الفئات"
}
REV_OFFER_TYPES_MAP = {v: k for k, v in OFFER_TYPES_MAP.items()}

CHANNELS_MAP = {
    "browser": "متصفح المتجر",
    "app": "تطبيق المتجر",
    "browser_and_application": "متصفح وتطبيق المتجر",
    "pos": "سلة بوينت"
}
REV_CHANNELS_MAP = {v: k for k, v in CHANNELS_MAP.items()}

APPLIED_TO_MAP = {
    "all": "جميع المنتجات",
    "product": "منتجات مختارة",
    "category": "تصنيفات مختارة",
    "paymentMethod": "طرق دفع مختارة",
    "brand": "علامات تجارية مختارة",
    "tag": "وسوم مختارة"
}
REV_APPLIED_TO_MAP = {v: k for k, v in APPLIED_TO_MAP.items()}

def safe_parse_date(date_str: Optional[str]) -> Optional[datetime]:
    if not date_str: return None
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%d-%m-%Y', '%a %b %d %Y %H:%M:%S', '%Y-%m-%dT%H:%M:%S'):
        try:
            clean_str = re.sub(r' GMT.*$', '', str(date_str)).replace('T', ' ')
            return datetime.strptime(clean_str[:19], fmt.replace('T', ' '))
        except (ValueError, TypeError): pass
    return None

def parse_products_cleanly(offer_section: Dict) -> str:
    """تحليل دقيق للأصناف المشمولة لمنع تداخل اسم العرض"""
    if not offer_section or not isinstance(offer_section, dict):
        return "جميع الأصناف المشمولة"
    
    clean_elements = []
    products = offer_section.get('products', [])
    if products and isinstance(products, list):
        for p in products:
            if isinstance(p, dict):
                clean_elements.append(f"• صنف: {p.get('name', 'غير معرف')} [ID: {p.get('id', 'N/A')}] [SKU: {p.get('sku', 'N/A')}]")
            else:
                clean_elements.append(f"• معرف منتج رقم: {p}")
                
    categories = offer_section.get('categories', [])
    if categories and isinstance(categories, list):
        for c in categories:
            if isinstance(c, dict):
                clean_elements.append(f"• تصنيف: {c.get('name', 'غير معرف')} [ID: {c.get('id', 'N/A')}]")
            else:
                clean_elements.append(f"• معرف تصنيف رقم: {c}")
                
    return "\n".join(clean_elements) if clean_elements else "جميع الأصناف المشمولة"

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

def style_excel_file(ws, is_template=False, header_color="0F1C2E"):
    header_fill = PatternFill(start_color=header_color, end_color=header_color, fill_type="solid")
    header_font = Font(name="Segoe UI", size=11, bold=True, color="0F1C2E" if header_color == "00EBCF" else "FFFFFF")
    center_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin_border = Border(
        left=Side(style='thin', color='DDDDDD'), right=Side(style='thin', color='DDDDDD'),
        top=Side(style='thin', color='DDDDDD'), bottom=Side(style='thin', color='DDDDDD')
    )
    
    start_row = 2 if is_template else 1
    ws.row_dimensions[start_row].height = 28
    
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
        ws.column_dimensions[col_letter].width = min(max(max_len + 4, 16), 35)

def export_offers_to_excel(offers: List[Dict]) -> bytes:
    try:
        data = []
        for offer in offers:
            o_type = offer.get('offer_type', '')
            o_chan = offer.get('applied_channel', 'browser_and_application')
            o_app = offer.get('applied_to', 'product')
            
            buy_p = [str(p.get('id', p)) if isinstance(p, dict) else str(p) for p in offer.get('buy', {}).get('products', [])]
            get_p = [str(p.get('id', p)) if isinstance(p, dict) else str(p) for p in offer.get('get', {}).get('products', [])]
            
            data.append({
                'المعرف': offer.get('id', ''), 'اسم العرض': offer.get('name', ''), 
                'النوع': OFFER_TYPES_MAP.get(o_type, o_type), 'منصة العرض': CHANNELS_MAP.get(o_chan, o_chan),
                'تطبيق العرض على': APPLIED_TO_MAP.get(o_app, o_app), 'الحالة': offer.get('status', 'active'),
                'مع كوبون التخفيض': 'نعم' if offer.get('applied_with_coupon', False) else 'لا',
                'تاريخ البدء': offer.get('start_date', ''), 'تاريخ الانتهاء': offer.get('expiry_date', ''),
                'الحد الأقصى للخصم': offer.get('max_discount_amount', 0),
                'الحد الأدنى لمبلغ الشراء': offer.get('min_purchase_amount', 0),
                'الحد الأدنى لكمية المنتجات': offer.get('min_items_count', 0),
                'Buy_Type': offer.get('buy', {}).get('type', 'product'),
                'كمية الشراء (X)': offer.get('buy', {}).get('quantity', 1), 'منتجات الشراء': ', '.join(buy_p),
                'Get_Type': offer.get('get', {}).get('type', 'product'),
                'الكمية المجانية (Y)': offer.get('get', {}).get('quantity', 1), 'المنتجات المجانية': ', '.join(get_p),
                'قيمة أو نسبة الخصم': offer.get('get', {}).get('discount_amount', 0), 'نص رسالة العرض': offer.get('message', '')
            })
        df = pd.DataFrame(data)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
            style_excel_file(writer.sheets['Sheet1'], is_template=False, header_color="0F1C2E")
        return buffer.getvalue()
    except Exception as e:
        st.error(f"⚠️ خطأ في تصدير العروض: {str(e)}")
        return b""

def generate_salla_excel_template() -> bytes:
    from openpyxl import Workbook
    output = io.BytesIO()
    wb = Workbook()
    ws = wb.active
    ws.title = "قائمة العروض"
    
    ws.append(["💡 إرشادات سلة: يرجى اختيار القيم بدقة من القوائم المنسدلة الظاهرة داخل الخلايا لضمان نجاح التدوين والربط السحابي."])
    ws.merge_cells('A1:U1')
    ws.row_dimensions[1].height = 24
    
    columns = [
        "Action", "Offer_ID", "Offer_Name", "Offer_Type", "Applied_Channel",
        "Applied_To", "With_Coupon", "Offer_Status", "Start_Date_Time", "Expiry_Date_Time",
        "Max_Discount_Amount", "Min_Purchase_Amount", "Min_Items_Count",
        "Buy_Type", "Buy_Quantity", "Buy_Products_IDs", "Get_Type", "Get_Quantity", 
        "Discount_Type", "Discount_Amount", "Get_Products_IDs", "Offer_Message"
    ]
    ws.append(columns)
    ws.append(["create", "", "8009 / عرض 1+1 مجاناً", "اذا اشترى العميل X يحصل على Y", "متصفح وتطبيق المتجر", "منتجات مختارة", "لا", "active", "2026-06-24 12:00:00", "2026-12-31 23:59:59", 0, 100, 0, "product", 1, "12345", "product", 1, "منتج مجاني", 0, "67890", "عرض 1+1 مجاناً"])
    
    style_excel_file(ws, is_template=True, header_color="00ddc2")
    
    # حقن القوائم المنسدلة لـ Buy_Type و Get_Type و نطاق التطبيق والنوع والمنصات
    types_str = ",".join(OFFER_TYPES_MAP.values())
    channels_str = ",".join(CHANNELS_MAP.values())
    applied_str = ",".join(APPLIED_TO_MAP.values())
    
    dv_action = DataValidation(type="list", formula1='"create,update,delete"', allow_blank=True)
    ws.add_data_validation(dv_action); dv_action.add("A3:A100")
    
    dv_type = DataValidation(type="list", formula1=f'"{types_str}"', allow_blank=True)
    ws.add_data_validation(dv_type); dv_type.add("D3:D100")
    
    dv_channel = DataValidation(type="list", formula1=f'"{channels_str}"', allow_blank=True)
    ws.add_data_validation(dv_channel); dv_channel.add("E3:E100")
    
    dv_applied = DataValidation(type="list", formula1=f'"{applied_str}"', allow_blank=True)
    ws.add_data_validation(dv_applied); dv_applied.add("F3:F100")
    
    dv_coupon = DataValidation(type="list", formula1='"نعم,لا"', allow_blank=True)
    ws.add_data_validation(dv_coupon); dv_coupon.add("G3:G100")
    
    dv_status = DataValidation(type="list", formula1='"active,inactive"', allow_blank=True)
    ws.add_data_validation(dv_status); dv_status.add("H3:H100")
    
    dv_btype = DataValidation(type="list", formula1='"product,category"', allow_blank=True)
    ws.add_data_validation(dv_btype); dv_btype.add("N3:N100")
    
    dv_gtype = DataValidation(type="list", formula1='"product,category"', allow_blank=True)
    ws.add_data_validation(dv_gtype); dv_gtype.add("Q3:Q100")
    
    wb.save(output)
    return output.getvalue()

def process_excel_import(df: pd.DataFrame) -> Dict:
    results = {"success": [], "errors": []}
    headers = get_headers()
    if not headers:
        results["errors"].append("❌ الرجاء إدخال مفتاح الربط أولاً")
        return results
    
    for idx, row in df.iterrows():
        if row.isna().all() or str(row.iloc[0]).strip().startswith("📋") or str(row.iloc[0]).strip().startswith("💡"): continue
        try:
            action = str(row.get('Action', 'create')).strip().lower()
            offer_name = str(row.get('Offer_Name', 'عرض جديد')).strip()
            offer_id = row.get('Offer_ID')
            if offer_id and pd.notna(offer_id): offer_id = int(float(offer_id))
            
            api_type = REV_OFFER_TYPES_MAP.get(str(row.get('Offer_Type', '')).strip(), "buy_x_get_y")
            api_channel = REV_CHANNELS_MAP.get(str(row.get('Applied_Channel', '')).strip(), "browser_and_application")
            api_applied = REV_APPLIED_TO_MAP.get(str(row.get('Applied_To', '')).strip(), "product")
            
            offer_data = {
                "name": offer_name, "offer_type": api_type, "applied_channel": api_channel, "applied_to": api_applied,
                "start_date": str(row.get('Start_Date_Time', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))),
                "expiry_date": str(row.get('Expiry_Date_Time', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))),
                "message": str(row.get('Offer_Message', '')).strip(), "status": str(row.get('Offer_Status', 'active')).strip().lower(),
                "applied_with_coupon": str(row.get('With_Coupon', 'لا')).strip() == 'نعم',
                "max_discount_amount": float(row.get('Max_Discount_Amount', 0) or 0),
                "min_purchase_amount": float(row.get('Min_Purchase_Amount', 0) or 0),
                "min_items_count": int(row.get('Min_Items_Count', 0) or 0),
                "buy": {"type": str(row.get('Buy_Type', 'product')).strip(), "quantity": int(row.get('Buy_Quantity', 1))},
                "get": {"type": str(row.get('Get_Type', 'product')).strip(), "quantity": int(row.get('Get_Quantity', 1)), "discount_type": "percentage" if "نسبة" in str(row.get('Discount_Type', '')) else "free-product"}
            }
            
            for key, col_name in [("buy", "Buy_Products_IDs"), ("get", "Get_Products_IDs")]:
                p_str = str(row.get(col_name, '')).strip()
                if p_str and p_str != 'nan':
                    ids = [int(p) for p in re.split(r'[,\s;]+', p_str) if p.strip().isdigit()]
                    if ids: offer_data[key]["products"] = ids
                    
            disc_amt = float(row.get('Discount_Amount', 0) or 0)
            if disc_amt > 0: offer_data["get"]["discount_amount"] = disc_amt

            if action == 'create':
                res = safe_api_request("POST", SALLA_API_URL, headers, json=offer_data)
                if res: results["success"].append(f"✅ تم إنشاء العرض: {offer_name}")
            elif action == 'update' and offer_id:
                res = safe_api_request("PUT", f"{SALLA_API_URL}/{offer_id}", headers, json=offer_data)
                if res: results["success"].append(f"✅ تم تحديث العرض ID: {offer_id}")
            elif action == 'delete' and offer_id:
                res = safe_api_request("DELETE", f"{SALLA_API_URL}/{offer_id}", headers)
                if res: results["success"].append(f"✅ تم حذف العرض ID: {offer_id}")
        except Exception as e:
            results["errors"].append(f"❌ خطأ في الصف {idx+1}: {str(e)}")
    return results

def export_products_to_excel(products: List[Dict]) -> bytes:
    try:
        data = []
        for p in products:
            price = get_flat_price(p.get('price', 0))
            sale_price = get_flat_price(p.get('sale_price', 0))
            regular_price = get_flat_price(p.get('regular_price', 0))
            base_price = regular_price if regular_price > 0 else price
            
            promo = p.get('promotion', {})
            promo_title = p.get('promotion_title') or (promo.get('title') if isinstance(promo, dict) else '') or "لا يوجد"
            promo_sub = (promo.get('sub_title') if isinstance(promo, dict) else '') or "لا يوجد"
            
            sale_start = p.get('sale_start') or (p.get('sale_price', {}).get('start_at') if isinstance(p.get('sale_price'), dict) else None) or "غير محدد"
            sale_end = p.get('sale_end') or (p.get('sale_price', {}).get('expired_at') if isinstance(p.get('sale_price'), dict) else None) or "غير محدد"
            
            data.append({
                'المعرف': p.get('id', ''), 'الاسم': p.get('name', ''), 'SKU': p.get('sku', ''),
                'السعر الأساسي': base_price, 'السعر المخفض': sale_price if sale_price > 0 else 'لا يوجد',
                'خاضع للضريبة': 'نعم' if p.get('with_tax', True) else 'لا',
                'العنوان الترويجي': promo_title, 'العنوان الفرعي': promo_sub,
                'تاريخ بداية التخفيض': sale_start, 'تاريخ نهاية التخفيض': sale_end,
                'المخزون': p.get('quantity', 0), 'المبيعات': p.get('sold_quantity', 0),
                'الحالة': 'معروض' if p.get('status') == 'sale' else 'مخفي'
            })
        df = pd.DataFrame(data)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
            style_excel_file(writer.sheets['Sheet1'], is_template=False, header_color="0F1C2E")
        return buffer.getvalue()
    except Exception as e:
        st.error(f"⚠️ خطأ في تصدير المنتجات: {str(e)}")
        return b""

def update_product_status(product_id: int, status: str) -> bool:
    headers = get_headers()
    if not headers: return False
    url = f"https://api.salla.dev/admin/v2/products/{product_id}/status"
    res = safe_api_request("POST", url, headers, json={"status": status})
    return res is not None
