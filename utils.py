import streamlit as st
import pandas as pd
import io
import requests
import json
import logging
import re
from datetime import datetime
from typing import Optional, List, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SALLA_API_URL = "https://api.salla.dev/admin/v2/specialoffers"

def safe_parse_date(date_str: Optional[str]) -> Optional[datetime]:
    if not date_str: return None
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%a %b %d %Y %H:%M:%S'):
        try:
            # تنظيف السلسلة النصية من صيغ المناطق الزمنية الزائدة إن وجدت
            clean_str = re.sub(r' GMT.*$', '', str(date_str))
            return datetime.strptime(clean_str, fmt)
        except (ValueError, TypeError): pass
    return None

def parse_products_cleanly(offer_section: Dict) -> str:
    """تحليل شامل وقراءة ذكية للمنتجات أو التصنيفات المشمولة بالعرض بناءً على وثائق سلة"""
    if not offer_section or not isinstance(offer_section, dict):
        return "كل منتجات المتجر"
    
    clean_elements = []
    
    # 1. التحقق من وجود منتجات مباشرة
    products = offer_section.get('products', [])
    if products and isinstance(products, list):
        for p in products:
            if isinstance(p, dict):
                clean_elements.append(f"• منتج: {p.get('name', 'غير معرف')} [ID: {p.get('id', 'N/A')}]")
            else:
                clean_elements.append(f"• معرف منتج رقم: {p}")
                
    # 2. التحقق من وجود تصنيفات (Categories) كما هو موضح في ملف Special Offer.md
    categories = offer_section.get('categories', [])
    if categories and isinstance(categories, list):
        for c in categories:
            if isinstance(c, dict):
                clean_elements.append(f"• تصنيف: {c.get('name', 'غير معرف')} [ID: {c.get('id', 'N/A')}]")
            else:
                clean_elements.append(f"• معرف تصنيف رقم: {c}")
                
    return "\n".join(clean_elements) if clean_elements else "كل المنتجات / غير محدد بدقة"

def get_flat_price(price_field: Any) -> float:
    """استخراج القيمة الرقمية للسعر سواء كان رقماً مباشراً أو كائناً يحتوي على amount وفقاً لـ Product.md"""
    if not price_field:
        return 0.0
    if isinstance(price_field, dict):
        return float(price_field.get('amount', 0.0))
    try:
        return float(price_field)
    except (ValueError, TypeError):
        return 0.0

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
            df.to_excel(writer, index=False, sheet_name='قائمة العروض')
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
            data.append({
                'المعرف': p.get('id', ''), 'الاسم': p.get('name', ''), 'SKU': p.get('sku', ''),
                'السعر الأساسي': price, 'السعر المخفض': sale_price if sale_price > 0 else 'لا يوجد',
                'المخزون': p.get('quantity', 0), 'المبيعات': p.get('sold_quantity', 0),
                'الحالة': 'معروض' if p.get('status') == 'sale' else 'مخفي'
            })
        df = pd.DataFrame(data)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='قائمة المنتجات')
        return buffer.getvalue()
    except Exception as e:
        st.error(f"⚠️ خطأ في التصدير: {str(e)}")
        return b""

def generate_salla_excel_template() -> bytes:
    columns = [
        "Action", "Offer_ID", "Offer_Name", "Offer_Type", "Applied_Channel",
        "Applied_To", "With_Coupon", "Offer_Status", "Start_Date_Time", "Expiry_Date_Time", 
        "Buy_Type", "Buy_Quantity", "Buy_Products_IDs", "Get_Type", "Get_Quantity", 
        "Discount_Type", "Discount_Amount", "Get_Products_IDs", "Offer_Message"
    ]
    df = pd.DataFrame(columns=columns)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    return buffer.getvalue()

def process_excel_import(df: pd.DataFrame) -> Dict:
    results = {"success": [], "errors": []}
    headers = get_headers()
    if not headers:
        results["errors"].append("❌ الرجاء إدخال مفتاح الربط أولاً")
        return results
    
    for idx, row in df.iterrows():
        try:
            action = str(row.get('Action', 'create')).strip().lower()
            offer_name = str(row.get('Offer_Name', 'عرض جديد')).strip()
            offer_id = row.get('Offer_ID')
            if offer_id and pd.notna(offer_id):
                offer_id = int(float(offer_id))
            
            offer_data = {
                "name": offer_name,
                "offer_type": str(row.get('Offer_Type', 'buy_x_get_y')).strip(),
                "applied_channel": str(row.get('Applied_Channel', 'browser_and_application')).strip(),
                "applied_to": str(row.get('Applied_To', 'product')).strip(),
                "start_date": str(row.get('Start_Date_Time', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))),
                "expiry_date": str(row.get('Expiry_Date_Time', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))),
                "message": str(row.get('Offer_Message', '')).strip(),
                "status": str(row.get('Offer_Status', 'active')).strip().lower(),
                "applied_with_coupon": str(row.get('With_Coupon', 'لا')).strip() == 'نعم',
                "buy": {"type": str(row.get('Buy_Type', 'product')).strip(), "quantity": int(row.get('Buy_Quantity', 1))},
                "get": {"type": str(row.get('Get_Type', 'product')).strip(), "quantity": int(row.get('Get_Quantity', 1)), "discount_type": str(row.get('Discount_Type', 'percentage')).strip()}
            }
            
            for key, col_name in [("buy", "Buy_Products_IDs"), ("get", "Get_Products_IDs")]:
                p_str = str(row.get(col_name, '')).strip()
                if p_str and p_str != 'nan':
                    ids = [int(p) for p in re.split(r'[,\s;]+', p_str) if p.strip().isdigit()]
                    if ids: offer_data[key]["products"] = ids

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

def update_product_status(product_id: int, status: str) -> bool:
    """تحديث حالة ظهور المنتج بالمتجر بشكل سليم وتفادي خطأ 422"""
    headers = get_headers()
    if not headers: return False
    current = safe_api_request("GET", f"https://api.salla.dev/admin/v2/products/{product_id}", headers)
    if not current or not current.get('data'): return False
    p_data = current['data']
    
    # بناء كائن مسطح ومتوافق تماماً مع متطلبات تحديث سلة
    update_payload = {
        "status": status,
        "name": p_data.get('name'),
        "price": get_flat_price(p_data.get('price', 0))
    }
    
    # قنوات العرض مطلوبة عند النشر مجدداً للمتجر الإلكتروني والتطبيق
    update_payload["channels"] = p_data.get('channels', ["app", "browser"])
    if not update_payload["channels"]:
        update_payload["channels"] = ["app", "browser"]
        
    sale_amt = get_flat_price(p_data.get('sale_price', 0))
    if sale_amt > 0:
        update_payload['sale_price'] = sale_amt
        
    res = safe_api_request("PUT", f"https://api.salla.dev/admin/v2/products/{product_id}", headers, json=update_payload)
    return res is not None
