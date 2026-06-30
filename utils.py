import streamlit as st
import pandas as pd
import io
import os
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

# ==========================================
# 🛠️ دوال الأساسيات والربط
# ==========================================

def get_headers():
    token = st.session_state.get('access_token', '')
    if not token:
        st.warning("⚠️ الرجاء إدخال مفتاح الربط (Access Token)")
        return None
    # ✅ لا نضيف Content-Type هنا لأنه سيتم تحديده حسب نوع الطلب
    return {"Authorization": f"Bearer {token}"}

def safe_float(val: Any, default: float = 0.0) -> float:
    if val is None: return default
    try: return float(val)
    except (ValueError, TypeError): return default

def safe_parse_date(date_str: Optional[str]) -> Optional[datetime]:
    if not date_str: return None
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%a %b %d %Y %H:%M:%S', '%Y-%m-%dT%H:%M:%S'):
        try:
            clean_str = re.sub(r' GMT.*$', '', str(date_str)).replace('T', ' ')
            return datetime.strptime(clean_str[:19], fmt.replace('T', ' '))
        except (ValueError, TypeError): pass
    return None

def parse_products_cleanly(offer_section: Dict) -> str:
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
        return safe_float(price_field.get('amount', 0.0))
    return safe_float(price_field)

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

def style_excel_file(ws, is_template=False, header_color="0F1C2E"):
    header_fill = PatternFill(start_color=header_color, end_color=header_color, fill_type="solid")
    header_font = Font(name="Segoe UI", size=11, bold=True, color="0F1C2E" if header_color == "00EBCF" else "FFFFFF")
    center_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin_border = Border(left=Side(style='thin', color='DDDDDD'), right=Side(style='thin', color='DDDDDD'), top=Side(style='thin', color='DDDDDD'), bottom=Side(style='thin', color='DDDDDD'))
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

def prepare_import_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """تحضير DataFrame للاستيراد إلى سلة"""
    import_df = df.copy()
    
    # ✅ إعادة تسمية الأعمدة
    column_mapping = {
        'معرف المنتج': 'id',
        'SKU': 'sku',
        'اسم المنتج': 'name',
        'النوع': 'type',
        'نوع المنتج': 'product_type',
        'حالة المنتج': 'status',
        'السعر (SAR)': 'price',
        'السعر المخفض (SAR)': 'sale_price',
        'بداية التخفيض': 'sale_start',
        'نهاية التخفيض': 'sale_end',
        'كمية غير محدودة': 'unlimited_quantity',
        'خاضع للضريبة': 'with_tax',
        'سبب عدم الخضوع': 'tax_reason_code',
        'العنوان الترويجي': 'promotion_title',
        'العنوان الفرعي': 'promotion_subtitle'
    }
    import_df = import_df.rename(columns=column_mapping)
    
    # ✅ تحويل القيم إلى الصيغة المطلوبة
    # نوع المنتج
    product_type_mapping = {
        'منتج جاهز': 'product',
        'مجموعة منتجات': 'group_products',
        'بطاقة رقمية': 'codes',
        'منتج رقمي': 'digital',
        'أكل': 'food',
        'خدمة حسب الطلب': 'service',
        'منتج حجز': 'booking'
    }
    if 'product_type' in import_df.columns:
        import_df['product_type'] = import_df['product_type'].map(product_type_mapping).fillna('product')
    
    # حالة المنتج
    status_mapping = {
        'معروض': 'sale',
        'مخفي': 'hidden'
    }
    if 'status' in import_df.columns:
        import_df['status'] = import_df['status'].map(status_mapping).fillna('sale')
    
    # خاضع للضريبة
    tax_mapping = {
        'نعم': 'true',
        'لا': 'false'
    }
    if 'with_tax' in import_df.columns:
        import_df['with_tax'] = import_df['with_tax'].map(tax_mapping).fillna('true')
    
    # كمية غير محدودة
    unlimited_mapping = {
        'نعم': 'true',
        'لا': 'false'
    }
    if 'unlimited_quantity' in import_df.columns:
        import_df['unlimited_quantity'] = import_df['unlimited_quantity'].map(unlimited_mapping).fillna('false')
    
    # ✅ تنظيف البيانات الفارغة
    import_df = import_df.fillna('')
    
    return import_df

def create_products_template(products=None) -> bytes:
    """إنشاء قالب استيراد منتجات مطابق تماماً لهيكل سلة الأصلي"""
    try:
        from openpyxl import Workbook
        # هذا هو الهيكل الفعلي لأعمدة سلة التي تتوقعها المنصة
        headers = [
            "No.", "النوع", "أسم المنتج", "تصنيف المنتج", "صورة المنتج", 
            "وصف صورة المنتج", "نوع المنتج", "سعر المنتج", "الوصف", 
            "هل يتطلب شحن؟", "رمز المنتج sku", "سعر التكلفة", 
            "السعر المخفض", "تاريخ بداية التخفيض", "تاريخ نهاية التخفيض",
            "اقصي كمية لكل عميل", "إخفاء خيار تحديد الكمية", "اضافة صورة عند الطلب",
            "السعر المخفض", "وحدة الوزن", "حالة المنتج","الماركة","العنوان الترويجي",
            "تثبيت المنتج", "الباركود", "السعرات الحرارية","MPN","GTIN",
            "خاضع للضريبة ؟", "سبب عدم الخضوع للضريبة"
        ]
        wb = Workbook()
        ws = wb.active
        ws.title = "Salla Products Template Sheet"
        ws.append(headers)
        
        # إذا كان هناك بيانات موجودة يتم ملؤها
        if products:
            for p in products:
                ws.append([
                    p.get('id', ''), 'منتج', p.get('name', ''), '', '', '', 
                    'منتج جاهز', p.get('price', 0), '', 'نعم', p.get('sku', ''), 
                    '', p.get('sale_price', ''), p.get('sale_start', ''), p.get('sale_end', '')
                ])
        
        output = io.BytesIO()
        wb.save(output)
        return output.getvalue()
    except Exception as e:
        st.error(f"❌ خطأ في إنشاء القالب: {str(e)}")
        return b""
        
# ==========================================
# 🎁 دوال العروض الخاصة
# ==========================================

def export_offers_to_excel(offers: List[Dict]) -> bytes:
    try:
        data = []
        for offer in offers:
            o_type = offer.get('offer_type', '')
            o_chan = offer.get('applied_channel', 'browser_and_application')
            o_app = offer.get('applied_to', 'product')
            buy_p = [str(p.get('id', p)) if isinstance(p, dict) else str(p) for p in offer.get('buy', {}).get('products', [])]
            get_p = [str(p.get('id', p)) if isinstance(p, dict) else str(p) for p in offer.get('get', {}).get('products', [])]
            cust_groups = [str(g.get('id', g)) if isinstance(g, dict) else str(g) for g in offer.get('customer_groups', [])]
            
            data.append({
                'المعرف': offer.get('id', ''), 'اسم العرض': offer.get('name', ''), 
                'النوع': OFFER_TYPES_MAP.get(o_type, o_type), 'منصة العرض': CHANNELS_MAP.get(o_chan, o_chan),
                'تطبيق العرض على': APPLIED_TO_MAP.get(o_app, o_app), 'الحالة': offer.get('status', 'active'),
                'مع كوبون': 'نعم' if offer.get('applied_with_coupon', False) else 'لا',
                'مجموعات العملاء المشمولة': ', '.join(cust_groups),
                'تاريخ البدء': offer.get('start_date', ''), 'تاريخ الانتهاء': offer.get('expiry_date', ''),
                'الحد الأقصى للخصم': safe_float(offer.get('max_discount_amount', 0)),
                'الحد الأدنى لمبلغ الشراء': safe_float(offer.get('min_purchase_amount', 0)),
                'الحد الأدنى لكمية المنتجات': int(safe_float(offer.get('min_items_count', 0))),
                'Buy_Type': 'تصنيف' if offer.get('buy', {}).get('type') == 'category' else 'منتج',
                'كمية الشراء (X)': offer.get('buy', {}).get('quantity', 1), 'منتجات الشراء': ', '.join(buy_p),
                'Get_Type': 'تصنيف' if offer.get('get', {}).get('type') == 'category' else 'منتج',
                'كمية الهدية (Y)': offer.get('get', {}).get('quantity', 1), 
                'Discount_Type': 'خصم بنسبة' if offer.get('get', {}).get('discount_type') == 'percentage' else 'منتج مجاني',
                'قيمة أو نسبة الخصم': safe_float(offer.get('get', {}).get('discount_amount', 0)), 
                'منتجات الهدية': ', '.join(get_p), 'الرسالة': offer.get('message', '')
            })
        df = pd.DataFrame(data)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
            style_excel_file(writer.sheets['Sheet1'], is_template=False, header_color="0F1C2E")
        return buffer.getvalue()
    except Exception as e:
        return b""

def generate_salla_excel_template() -> bytes:
    from openpyxl import Workbook
    output = io.BytesIO()
    wb = Workbook()
    ws = wb.active
    ws.title = "قائمة العروض"
    ws.append(["💡 إرشادات سلة المحدثة: تم تصحيح أماكن القوائم المنسدلة لتعمل باللغة العربية كلياً وبشكل صحيح."])
    ws.merge_cells('A1:W1')
    ws.row_dimensions[1].height = 24
    columns = [
        "Action", "Offer_ID", "Offer_Name", "Offer_Type", "Applied_Channel",
        "Applied_To", "With_Coupon", "Customer_Groups", "Offer_Status", "Start_Date_Time", "Expiry_Date_Time",
        "Max_Discount_Amount", "Min_Purchase_Amount", "Min_Items_Count",
        "Buy_Type", "Buy_Quantity", "Buy_Products_IDs", "Get_Type", "Get_Quantity", 
        "Discount_Type", "Discount_Amount", "Get_Products_IDs", "Offer_Message"
    ]
    ws.append(columns)
    ws.append(["create", "", "عرض بلسم المطور", "اذا اشترى العميل X يحصل على Y", "متصفح وتطبيق المتجر", "منتجات مختارة", "لا", "10239", "active", "2026-06-24 12:00:00", "2026-12-31 23:59:59", 0, 150, 0, "منتج", 1, "12345", "منتج", 1, "منتج مجاني", 0, "67890", "خصم بلسم المميز"])
    style_excel_file(ws, is_template=True, header_color="00EBCF")
    
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
    ws.add_data_validation(dv_status); dv_status.add("I3:I100")
    dv_btype = DataValidation(type="list", formula1='"منتج,تصنيف"', allow_blank=True)
    ws.add_data_validation(dv_btype); dv_btype.add("O3:O100")
    dv_gtype = DataValidation(type="list", formula1='"منتج,تصنيف"', allow_blank=True)
    ws.add_data_validation(dv_gtype); dv_gtype.add("R3:R100")
    dv_dtype = DataValidation(type="list", formula1='"منتج مجاني,خصم بنسبة"', allow_blank=True)
    ws.add_data_validation(dv_dtype); dv_dtype.add("T3:T100")
    
    wb.save(output)
    return output.getvalue()

def process_excel_import(df: pd.DataFrame) -> Dict:
    results = {"success": [], "errors": []}
    headers = get_headers()
    if not headers: return results
    for idx, row in df.iterrows():
        if row.isna().all() or str(row.iloc[0]).strip().startswith("📋") or str(row.iloc[0]).strip().startswith("💡"): continue
        try:
            action = str(row.get('Action', 'create')).strip().lower()
            offer_name = str(row.get('Offer_Name', 'عرض جديد')).strip()
            offer_id = row.get('Offer_ID')
            if offer_id and pd.notna(offer_id): offer_id = int(float(offer_id))
            
            api_type = REV_OFFER_TYPES_MAP.get(str(row.get('Offer_Type', '')).strip(), "buy_x_get_y")
            api_channel = REV_CHANNELS_MAP.get(str(row.get('Applied_Channel', '')).strip(), "browser_and_application")
            api_applied_to = REV_APPLIED_TO_MAP.get(str(row.get('Applied_To', '')).strip(), "product")
            b_type_raw = str(row.get('Buy_Type', 'منتج')).strip()
            api_buy_type = "category" if b_type_raw == "تصنيف" else "product"
            g_type_raw = str(row.get('Get_Type', 'منتج')).strip()
            api_get_type = "category" if g_type_raw == "تصنيف" else "product"
            disc_type_raw = str(row.get('Discount_Type', '')).strip()
            api_disc_type = "percentage" if disc_type_raw == "خصم بنسبة" else "free-product"
            
            cg_str = str(row.get('Customer_Groups', '')).strip()
            cg_ids = [int(g.strip()) for g in re.split(r'[,\s;]+', cg_str) if g.strip().isdigit()] if cg_str and cg_str != 'nan' else []
            
            offer_data = {
                "name": offer_name, "offer_type": api_type, "applied_channel": api_channel, "applied_to": api_applied_to,
                "start_date": str(row.get('Start_Date_Time', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))),
                "expiry_date": str(row.get('Expiry_Date_Time', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))),
                "message": str(row.get('Offer_Message', '')).strip(), "status": str(row.get('Offer_Status', 'active')).strip().lower(),
                "applied_with_coupon": str(row.get('With_Coupon', 'لا')).strip() == 'نعم',
                "customer_groups": cg_ids,
                "max_discount_amount": safe_float(row.get('Max_Discount_Amount', 0)),
                "min_purchase_amount": safe_float(row.get('Min_Purchase_Amount', 0)),
                "min_items_count": int(safe_float(row.get('Min_Items_Count', 0))),
                "buy": {"type": api_buy_type, "quantity": int(row.get('Buy_Quantity', 1))},
                "get": {"type": api_get_type, "quantity": int(row.get('Get_Quantity', 1)), "discount_type": api_disc_type}
            }
            for key, col_name in [("buy", "Buy_Products_IDs"), ("get", "Get_Products_IDs")]:
                p_str = str(row.get(col_name, '')).strip()
                if p_str and p_str != 'nan':
                    ids = [int(p) for p in re.split(r'[,\s;]+', p_str) if p.strip().isdigit()]
                    if ids: offer_data[key]["products"] = ids
            disc_amt = safe_float(row.get('Discount_Amount', 0))
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

# ==========================================
# 📦 دوال المنتجات والصور والضرائب
# ==========================================

def update_product_status(product_id: int, status: str) -> bool:
    headers = get_headers()
    if not headers: return False
    url = f"https://api.salla.dev/admin/v2/products/{product_id}/status"
    res = safe_api_request("POST", url, headers, json={"status": status})
    return res is not None

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
                'السعر الأساسي الأصل': base_price, 'السعر المخفض الحالي': sale_price if sale_price > 0 else 'لا يوجد',
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
        return b""

def fill_salla_template(products: List[Dict], template_path: str = "Salla_Products_Template.xlsx") -> bytes:
    """
    يقوم بفتح القالب الأصلي لسلة وملء البيانات فيه مباشرة بشكل متوافق 100%
    ملاحظة: يجب أن تضع ملف القالب الأصلي في مجلد المشروع باسم Salla_Products_Template.xlsx
    """
    try:
        import os
        import openpyxl
        import io

        # 1. فتح القالب الأصلي
        if not os.path.exists(template_path):
            st.error(f"❌ لم يتم العثور على ملف القالب: {template_path}")
            return b""
            
        wb = openpyxl.load_workbook(template_path)
        ws = wb["Salla Products Template Sheet"] # الاسم الدقيق للورقة
        
        # ✅ 2. مسح أي بيانات تجريبية موجودة في القالب لمنع تعارض البيانات
        if ws.max_row >= 3:
            ws.delete_rows(3, ws.max_row - 2)
        
        start_row = 3 
        
        # ✅ 3. كتابة البيانات بالكلمات الإلزامية التي يتوقعها نظام سلة
        for i, p in enumerate(products):
            current_row = start_row + i
            price = get_flat_price(p.get('price', 0))
            sale_price = get_flat_price(p.get('sale_price', 0))
            
            # ✅ إصلاح 1: استخراج العنوان الترويجي بدقة من القاموس المتداخل
            promo_obj = p.get('promotion', {})
            promo_title = p.get('promotion_title') or (promo_obj.get('title') if isinstance(promo_obj, dict) else '')
            
            # ✅ إصلاح 2: استخراج تواريخ التخفيض بدقة لمنع مسحها عند التحديث
            sale_start = p.get('sale_start') or (p.get('sale_price', {}).get('start_at') if isinstance(p.get('sale_price'), dict) else None)
            sale_end = p.get('sale_end') or (p.get('sale_price', {}).get('expired_at') if isinstance(p.get('sale_price'), dict) else None)
            
            # قص الوقت والاكتفاء بالتاريخ YYYY-MM-DD ليتوافق مع الإكسيل
            if sale_start and isinstance(sale_start, str): sale_start = sale_start[:10]
            if sale_end and isinstance(sale_end, str): sale_end = sale_end[:10]
            
            # ✅ إصلاح 3: استخدام None بدلاً من '' لمنع رفض سلة للمنتجات الجديدة (الملف فارغ)
            p_id = p.get('id')
            ws.cell(row=current_row, column=1).value = p_id if p_id else None # No. (إلزامي أن يكون None للمنتجات الجديدة)
            
            ws.cell(row=current_row, column=2).value = 'منتج'                 # النوع
            ws.cell(row=current_row, column=3).value = p.get('name') or 'بدون اسم' # أسم المنتج
            ws.cell(row=current_row, column=7).value = 'منتج جاهز'            # نوع المنتج
            ws.cell(row=current_row, column=8).value = price if price > 0 else 0 # سعر المنتج
            ws.cell(row=current_row, column=10).value = 'نعم'                 # هل يتطلب شحن؟
            
            p_sku = p.get('sku')
            ws.cell(row=current_row, column=11).value = p_sku if p_sku else None # رمز المنتج
            
            ws.cell(row=current_row, column=13).value = sale_price if sale_price > 0 else None # السعر المخفض
            
            # ✅ إضافة أعمدة التواريخ (14 و 15) للحفاظ عليها في المتجر
            ws.cell(row=current_row, column=14).value = sale_start if sale_start else None
            ws.cell(row=current_row, column=15).value = sale_end if sale_end else None
            
            ws.cell(row=current_row, column=19).value = 1                     # الوزن
            ws.cell(row=current_row, column=20).value = 'kg'                  # وحدة الوزن
            ws.cell(row=current_row, column=21).value = 'متاح' if p.get('status', 'sale') == 'sale' else 'مخفي'
            
            # وضع العنوان الترويجي
            ws.cell(row=current_row, column=23).value = promo_title if promo_title else None
            
            ws.cell(row=current_row, column=29).value = 'نعم' if p.get('with_tax', True) else 'لا'
            
            if not p.get('with_tax', True):
                ws.cell(row=current_row, column=30).value = p.get('tax_exemption_cause') or 'الأدوية والمعدات الطبية'
            else:
                ws.cell(row=current_row, column=30).value = None
                
        output = io.BytesIO()
        wb.save(output)
        return output.getvalue()
    except Exception as e:
        st.error(f"❌ خطأ في ملء القالب: {str(e)}")
        return b""

def upload_product_image_api(product_id: int, image_bytes: bytes, filename: str) -> bool:
    """رفع وإرفاق صورة للمنتج بصيغة multipart/form-data كما تتطلب منصة سلة"""
    token = st.session_state.get('access_token', '')
    if not token: return False
    
    headers = {"Authorization": f"Bearer {token}"}
    url = f"https://api.salla.dev/admin/v2/products/{product_id}/images"
    
    # يجب إرسال الصورة كـ tuple (filename, bytes, content_type)
    files = {
        'photo': (filename, image_bytes, 'image/jpeg')
    }
    
    try:
        response = requests.post(url, headers=headers, files=files, timeout=30)
        if response.status_code >= 400:
            try: error_detail = response.json()
            except: error_detail = response.text
            st.error(f"⚠️ خطأ في رفع الصورة: {error_detail}")
            return False
        return True
    except Exception as e:
        st.error(f"⚠️ خطأ في الاتصال أثناء رفع الصورة: {str(e)}")
        return False

def attach_product_image_api(product_id: int, image_bytes: bytes=None, filename: str=None, image_url: str=None) -> bool:
    token = st.session_state.get('access_token', '')
    if not token: return False
    headers = {"Authorization": f"Bearer {token}"}
    url = f"https://api.salla.dev/admin/v2/products/{product_id}/images"
    try:
        if image_url:
            headers["Content-Type"] = "application/json"
            response = requests.post(url, headers=headers, json={"original": image_url}, timeout=30)
        elif image_bytes and filename:
            files = {'photo': (filename, image_bytes, 'image/jpeg')}
            response = requests.post(url, headers=headers, files=files, timeout=30)
        else: return False
        return response.status_code < 400
    except Exception as e: return False

def update_product_promotions_secure(product_id: int, new_promo: str, new_sub: str, headers: dict) -> bool:
    """تحديث العناوين الترويجية والفرعية بشكل آمن مع حماية السعر الأصلي"""
    current_res = safe_api_request("GET", f"https://api.salla.dev/admin/v2/products/{product_id}", headers)
    if not current_res or not current_res.get('data'): return False
    
    p_data = current_res['data']
    price_val = get_flat_price(p_data.get('price', 0))
    sale_val = get_flat_price(p_data.get('sale_price', 0))
    regular_val = get_flat_price(p_data.get('regular_price', 0))
    
    base_price = regular_val if regular_val > 0 else price_val
    
    # ✅ إجبار إرسال العنوان الترويجي والفرعي كنصوص لسلة
    payload = {
        "name": p_data.get('name'),
        "price": base_price,
        "promotion_title": new_promo if new_promo else "",
        "promotion_subtitle": new_sub if new_sub else ""
    }
    
    # نحافظ على السعر المخفض إن وجد
    if sale_val > 0: 
        payload['sale_price'] = sale_val
        
    res = safe_api_request("PUT", f"https://api.salla.dev/admin/v2/products/{product_id}", headers, json=payload)
    return res is not None

def update_product_tax_secure(product_id: int, with_tax: bool, tax_cause: str, headers: dict) -> bool:
    current_res = safe_api_request("GET", f"https://api.salla.dev/admin/v2/products/{product_id}", headers)
    if not current_res or not current_res.get('data'): return False
    p_data = current_res['data']
    price_val = get_flat_price(p_data.get('price', 0))
    sale_val = get_flat_price(p_data.get('sale_price', 0))
    regular_val = get_flat_price(p_data.get('regular_price', 0))
    base_price = regular_val if regular_val > 0 else price_val
    
    payload = {"name": p_data.get('name'), "price": base_price, "with_tax": with_tax}
    if sale_val > 0: payload['sale_price'] = sale_val
    if not with_tax and tax_cause: payload["tax_exemption_cause"] = tax_cause
    res = safe_api_request("PUT", f"https://api.salla.dev/admin/v2/products/{product_id}", headers, json=payload)
    return res is not None

# ==========================================
# 🏢 دوال إدارة الفروع وتحديث الكميات
# ==========================================

def get_branches_list() -> List[Dict]:
    headers = get_headers()
    if not headers: return []
    res = safe_api_request("GET", "https://api.salla.dev/admin/v2/branches", headers)
    return res.get("data", []) if res else []

def generate_quantities_template() -> bytes:
    from openpyxl import Workbook
    from openpyxl.worksheet.datavalidation import DataValidation
    output = io.BytesIO()
    wb = Workbook()
    ws = wb.active
    ws.title = "تحديث الكميات"
    ws.append(["💡 إرشادات: ادخل رقم الـ SKU للمنتج، ومعرف الفرع، والكمية، ثم اختر نوع العملية من القائمة المنسدلة (increment للزيادة، decrement للنقصان، overwrite للاستبدال)."])
    ws.merge_cells('A1:D1')
    ws.row_dimensions[1].height = 24
    ws.append(["Product_SKU", "Branch_ID", "Quantity", "Mode"])
    ws.append(["SKU-123", "12345", 50, "increment"])
    style_excel_file(ws, is_template=True, header_color="00EBCF")
    dv_mode = DataValidation(type="list", formula1='"increment,decrement,overwrite"', allow_blank=False)
    ws.add_data_validation(dv_mode); dv_mode.add("D3:D1000")
    wb.save(output)
    return output.getvalue()

def process_quantities_import(df: pd.DataFrame) -> Dict:
    results = {"success": [], "errors": []}
    headers = get_headers()
    if not headers: return results
    quantities_payload = []
    for idx, row in df.iterrows():
        if row.isna().all() or str(row.iloc[0]).strip().startswith("💡"): continue
        try:
            sku = str(row.get('Product_SKU', '')).strip()
            branch_id = row.get('Branch_ID')
            quantity = int(safe_float(row.get('Quantity', 0)))
            mode = str(row.get('Mode', 'increment')).strip()
            if sku and pd.notna(branch_id):
                quantities_payload.append({"identifer": sku, "identifer_type": "sku", "branch_id": int(float(branch_id)), "quantity": quantity, "mode": mode})
        except Exception as e:
            results["errors"].append(f"❌ خطأ في قراءة الصف {idx+1}: {str(e)}")
            
    if quantities_payload:
        res = safe_api_request("POST", "https://api.salla.dev/admin/v2/products/quantities/bulk", headers, json={"products": quantities_payload})
        if res: results["success"].append(f"✅ تم تحديث كميات {len(quantities_payload)} سجل بنجاح!")
        else: results["errors"].append("❌ فشل إرسال طلب تحديث الكميات الجماعي.")
    return results

# ==========================================
# 👥 دوال العملاء والمجموعات
# ==========================================

def get_customers_list(keyword: str = "") -> Optional[Dict]:
    headers = get_headers()
    if not headers: return None
    url = "https://api.salla.dev/admin/v2/customers"
    params = {"keyword": keyword} if keyword else {}
    return safe_api_request("GET", url, headers, params=params)

def create_customer(customer_data: Dict) -> bool:
    headers = get_headers()
    if not headers: return False
    res = safe_api_request("POST", "https://api.salla.dev/admin/v2/customers", headers, json=customer_data)
    return res is not None

def update_customer_api(customer_id: int, customer_data: Dict) -> bool:
    headers = get_headers()
    if not headers: return False
    res = safe_api_request("PUT", f"https://api.salla.dev/admin/v2/customers/{customer_id}", headers, json=customer_data)
    return res is not None

def delete_customer_api(customer_id: int) -> bool:
    headers = get_headers()
    if not headers: return False
    res = safe_api_request("DELETE", f"https://api.salla.dev/admin/v2/customers/{customer_id}", headers)
    return res is not None

def get_customer_groups_list() -> Optional[Dict]:
    headers = get_headers()
    if not headers: return None
    return safe_api_request("GET", "https://api.salla.dev/admin/v2/customers/groups", headers)

def create_customer_group(group_data: Dict) -> bool:
    headers = get_headers()
    if not headers: return False
    res = safe_api_request("POST", "https://api.salla.dev/admin/v2/customers/groups", headers, json=group_data)
    return res is not None

def update_customer_group_api(group_id: int, group_data: Dict) -> bool:
    headers = get_headers()
    if not headers: return False
    res = safe_api_request("PUT", f"https://api.salla.dev/admin/v2/customers/groups/{group_id}", headers, json=group_data)
    return res is not None

def delete_customer_group_api(group_id: int) -> bool:
    headers = get_headers()
    if not headers: return False
    res = safe_api_request("DELETE", f"https://api.salla.dev/admin/v2/customers/groups/{group_id}", headers)
    return res is not None

def export_customers_to_excel(customers: List[Dict]) -> bytes:
    try:
        data = []
        for cust in customers:
            stats = cust.get('stats', {})
            orders_count = stats.get('orders_count', 0) if isinstance(stats, dict) else 0
            orders_amount = safe_float(stats.get('orders_amount', 0.0)) if isinstance(stats, dict) else 0.0
            data.append({
                'معرف العميل': cust.get('id', ''), 'الاسم الأول': cust.get('first_name', ''), 'اسم العائلة': cust.get('last_name', ''),
                'البريد الإلكتروني': cust.get('email', ''), 'الجنس': 'ذكر' if cust.get('gender') == 'male' else 'أنثى',
                'رمز الدولة': cust.get('mobile_code', ''), 'رقم الجوال': cust.get('mobile', ''), 'المدينة': cust.get('city', ''),
                'المنطقة / العنوان': cust.get('location', ''), 'عدد الطلبات': orders_count, 'إجمالي المشتريات (SAR)': orders_amount
            })
        df = pd.DataFrame(data)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
            style_excel_file(writer.sheets['Sheet1'], is_template=False, header_color="0F1C2E")
        return buffer.getvalue()
    except Exception as e: return b""

def export_customer_groups_to_excel(groups: List[Dict]) -> bytes:
    try:
        data = [{'معرف المجموعة': g.get('id', ''), 'اسم المجموعة': g.get('name', '')} for g in groups]
        df = pd.DataFrame(data)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
            style_excel_file(writer.sheets['Sheet1'], is_template=False, header_color="0F1C2E")
        return buffer.getvalue()
    except Exception as e: return b""

def generate_salla_new_products_file(products: List[Dict]) -> bytes:
    """
    إنشاء ملف إكسيل للمنتجات الجديدة متوافق 100% مع نموذج سلة الخاص بالإضافة 
    (يبدأ بعمود 'النوع' ولا يحتوي على عمود 'No.')
    """
    try:
        from openpyxl import Workbook
        import io

        wb = Workbook()
        ws = wb.active
        ws.title = "Salla Products Template Sheet"

        # الصف الأول: سلة تستخدمه كعنوان تجميعي
        row1 = ["بيانات المنتج"] + [""] * 39
        ws.append(row1)

        # الصف الثاني: أسماء الأعمدة الدقيقة للنموذج الجديد كما هي في منصة سلة
        headers = [
            "النوع ", "أسم المنتج", "تصنيف المنتج", "صورة المنتج", "وصف صورة المنتج",
            "نوع المنتج", "سعر المنتج", "الوصف", "هل يتطلب شحن؟", "رمز المنتج sku",
            "سعر التكلفة", "السعر المخفض", "تاريخ بداية التخفيض", "تاريخ نهاية التخفيض",
            "اقصي كمية لكل عميل", "إخفاء خيار تحديد الكمية", "اضافة صورة عند الطلب",
            "الوزن", "وحدة الوزن", "الماركة", "العنوان الترويجي", "تثبيت المنتج",
            "الباركود", "السعرات الحرارية", "MPN", "GTIN", "خاضع للضريبة ؟",
            "سبب عدم الخضوع للضريبة", "[1] الاسم", "[1] النوع", "[1] القيمة",
            "[1] الصورة / اللون", "[2] الاسم", "[2] النوع", "[2] القيمة",
            "[2] الصورة / اللون", "[3] الاسم", "[3] النوع", "[3] القيمة", "[3] الصورة / اللون"
        ]
        ws.append(headers)

        # ملء البيانات
        for p in products:
            price = get_flat_price(p.get('price', 0))
            is_taxable = p.get('with_tax', True)
            tax_cause = p.get('tax_exemption_cause', 'الأدوية والمعدات الطبية') if not is_taxable else ""
            
            row_data = [""] * len(headers)
            row_data[0] = 'منتج'                             # النوع
            row_data[1] = p.get('name', 'بدون اسم')          # أسم المنتج
            row_data[5] = 'منتج جاهز'                        # نوع المنتج
            row_data[6] = price if price > 0 else 0          # سعر المنتج
            row_data[8] = 'نعم'                              # هل يتطلب شحن؟
            row_data[9] = p.get('sku', "")                   # رمز المنتج sku
            row_data[17] = 1                                 # الوزن
            row_data[18] = 'kg'                              # وحدة الوزن
            row_data[20] = p.get('promotion_title', "")      # العنوان الترويجي
            row_data[26] = 'نعم' if is_taxable else 'لا'     # خاضع للضريبة ؟
            row_data[27] = tax_cause                         # سبب عدم الخضوع للضريبة
            
            ws.append(row_data)

        output = io.BytesIO()
        wb.save(output)
        return output.getvalue()
    except Exception as e:
        st.error(f"❌ خطأ في إنشاء قالب المنتجات الجديدة: {str(e)}")
        return b""
