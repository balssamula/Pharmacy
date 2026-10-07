import streamlit as st
import pandas as pd
import io
import os
import requests
import json
import threading
import logging
import re
import openpyxl
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from supabase import create_client
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.utils import get_column_letter
from streamlit.runtime.scriptrunner import add_script_run_ctx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Keep credentials in Streamlit Cloud > App settings > Secrets.
def _get_secret(name):
    try:
        value = st.secrets.get(name)
    except Exception:
        value = None
    return value or os.getenv(name)


@st.cache_resource
def get_supabase_client():
    url = _get_secret("SUPABASE_URL")
    key = _get_secret("SUPABASE_SECRET_KEY")
    if not url or not key:
        raise RuntimeError("Configure SUPABASE_URL and SUPABASE_SECRET_KEY in Streamlit Secrets.")
    return create_client(url, key)


def get_salla_store(merchant_id):
    merchant_id = str(merchant_id or "").strip()
    if not merchant_id:
        return None
    result = (
        get_supabase_client()
        .table("salla_stores")
        .select("*")
        .eq("merchant_id", merchant_id)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def list_salla_stores():
    result = (
        get_supabase_client()
        .table("salla_stores")
        .select("merchant_id,store_name,access_token,installed_at,expires_at,token_updated_at")
        .order("store_name")
        .execute()
    )
    return result.data or []


# Prevent two Streamlit sessions in this process from using one rotating token at once.
token_refresh_lock = threading.Lock()


def refresh_salla_token(merchant_id, force=False):
    """يجدد رمز متجر محدد ويحفظ access_token و refresh_token الجديدين."""
    merchant_id = str(merchant_id or "").strip()
    if not merchant_id:
        return False

    with token_refresh_lock:
        try:
            store = get_salla_store(merchant_id)
            if not store:
                return False

            expires_at = int(store.get("expires_at") or 0)

            # جدّد قبل الانتهاء بـ 48 ساعة.
            if not force and expires_at and expires_at > int(time.time()) + 48 * 3600:
                return store.get("access_token")

            refresh_token = store.get("refresh_token")
            if not refresh_token:
                return False

            client_id = _get_secret("SALLA_CLIENT_ID")
            client_secret = _get_secret("SALLA_CLIENT_SECRET")
            if not client_id or not client_secret:
                logger.error("Salla client credentials are missing from Streamlit Secrets")
                return False

            response = requests.post(
                "https://accounts.salla.sa/oauth2/token",
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=20,
            )

            if response.status_code != 200:
                try:
                    error_data = response.json()
                except ValueError:
                    error_data = {}

                if isinstance(error_data.get("error"), dict):
                    error_code = error_data["error"].get("code")
                    error_description = error_data["error"].get("message")
                else:
                    error_code = error_data.get("error")
                    error_description = error_data.get("error_description")

                logger.error(
                    "Salla refresh failed: HTTP %s, code=%s, description=%s",
                    response.status_code,
                    error_code,
                    error_description,
                )
                return False

            result = response.json()
            new_access = result.get("access_token")
            new_refresh = result.get("refresh_token")

            # لا نستبدل الرمز القديم برمز جديد ناقص.
            if not new_access or not new_refresh:
                logger.error("Salla refresh response did not contain both tokens")
                return False

            expires_value = result.get("expires")
            if expires_value:
                new_expires_at = int(expires_value)
            else:
                new_expires_at = int(time.time()) + int(
                    result.get("expires_in", 14 * 24 * 3600)
                )

            (
                get_supabase_client()
                .table("salla_stores")
                .update({
                    "access_token": new_access,
                    "refresh_token": new_refresh,
                    "expires_at": new_expires_at,
                    "token_updated_at": datetime.now(timezone.utc).isoformat(),
                })
                .eq("merchant_id", merchant_id)
                .execute()
            )

            if str(st.session_state.get("merchant_id", "")) == merchant_id:
                st.session_state["access_token"] = new_access

            return new_access

        except Exception:
            logger.exception("Error refreshing Salla token")
            return False
            
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

def safe_api_request(method, url, headers, json=None, **kwargs):
    try:
        headers = dict(headers or {})
        merchant_id = st.session_state.get("merchant_id")

        if merchant_id:
            token = refresh_salla_token(merchant_id)
            if token:
                headers["Authorization"] = f"Bearer {token}"

        response = requests.request(
            method,
            url,
            headers=headers,
            json=json,
            **kwargs,
        )

        if response.status_code == 401 and merchant_id:
            new_token = refresh_salla_token(merchant_id, force=True)

            if new_token:
                headers["Authorization"] = f"Bearer {new_token}"
                response = requests.request(
                    method,
                    url,
                    headers=headers,
                    json=json,
                    **kwargs,
                )

        if response.status_code < 400:
            return response.json()

        logger.error("Salla API request failed: HTTP %s", response.status_code)
        return None

    except Exception:
        logger.exception("Salla API request exception")
        return None

def style_excel_file(ws, is_template=True, header_color="0F1C2E"):
    header_fill = PatternFill(start_color=header_color, end_color=header_color, fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, name="Segoe UI", size=11)
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin_border = Border(left=Side(style='thin', color='DDDDDD'), right=Side(style='thin', color='DDDDDD'), 
                         top=Side(style='thin', color='DDDDDD'), bottom=Side(style='thin', color='DDDDDD'))

    for col in range(1, ws.max_column + 1):
        cell = ws.cell(row=1, column=col)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center_align
        cell.border = thin_border
        ws.column_dimensions[get_column_letter(col)].width = 22

    if ws.title in ["Salla Offers Template", "Salla Offers", "مسودة العروض"]:
        validations = {
            "A": '"إنشاء,تحديث,حذف"', "D": f'"{",".join(OFFER_TYPES_MAP.values())}"',
            "E": f'"{",".join(CHANNELS_MAP.values())}"', "F": f'"{",".join(APPLIED_TO_MAP.values())}"',
            "I": '"نعم,لا"', "N": '"منتج,تصنيف,ماركة"', "Q": '"منتج,تصنيف,ماركة"',
            "T": '"منتج مجاني,خصم بنسبة,مبلغ ثابت"', "W": '"نشط,غير نشط"'
        }
        for col_letter, formula1 in validations.items():
            if col_letter <= get_column_letter(ws.max_column):
                try:
                    dv = DataValidation(type="list", formula1=formula1, allow_blank=True)
                    ws.add_data_validation(dv)
                    dv.add(f"{col_letter}2:{col_letter}1000")
                except: pass

def prepare_import_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    import_df = df.copy()
    column_mapping = {
        'معرف المنتج': 'id', 'SKU': 'sku', 'اسم المنتج': 'name', 'النوع': 'type',
        'نوع المنتج': 'product_type', 'حالة المنتج': 'status', 'السعر (SAR)': 'price',
        'السعر المخفض (SAR)': 'sale_price', 'بداية التخفيض': 'sale_start',
        'نهاية التخفيض': 'sale_end', 'كمية غير محدودة': 'unlimited_quantity',
        'خاضع للضريبة': 'with_tax', 'سبب عدم الخضوع': 'tax_reason_code',
        'العنوان الترويجي': 'promotion_title', 'العنوان الفرعي': 'promotion_subtitle'
    }
    import_df = import_df.rename(columns=column_mapping)
    
    product_type_mapping = {'منتج جاهز': 'product', 'مجموعة منتجات': 'group_products', 'بطاقة رقمية': 'codes', 'منتج رقمي': 'digital', 'أكل': 'food', 'خدمة حسب الطلب': 'service', 'منتج حجز': 'booking'}
    if 'product_type' in import_df.columns: import_df['product_type'] = import_df['product_type'].map(product_type_mapping).fillna('product')
    
    status_mapping = {'معروض': 'sale', 'مخفي': 'hidden'}
    if 'status' in import_df.columns: import_df['status'] = import_df['status'].map(status_mapping).fillna('sale')
    
    tax_mapping = {'نعم': 'true', 'لا': 'false'}
    if 'with_tax' in import_df.columns: import_df['with_tax'] = import_df['with_tax'].map(tax_mapping).fillna('true')
    
    unlimited_mapping = {'نعم': 'true', 'لا': 'false'}
    if 'unlimited_quantity' in import_df.columns: import_df['unlimited_quantity'] = import_df['unlimited_quantity'].map(unlimited_mapping).fillna('false')
    
    import_df = import_df.fillna('')
    return import_df

# ==========================================
# 🎁 دوال العروض الخاصة (محسنة لخطأ 422)
# ==========================================

def generate_salla_excel_template() -> bytes:
    from openpyxl import Workbook
    headers = [
        "الإجراء", "معرف العرض", "اسم العرض", "نوع العرض", "المنصة", "تطبيق على", "تاريخ البدء", "تاريخ الانتهاء", 
        "تطبيق مع كوبون", "الحد الأقصى للخصم", "الحد الأدنى للشراء", "الحد الأدنى للكمية", 
        "مجموعات العملاء", "نوع شراء X", "كمية شراء X", "عناصر شراء X (IDs)", 
        "نوع عرض Y", "كمية عرض Y", "عناصر عرض Y (IDs)", "نوع الخصم", "قيمة الخصم", 
        "رسالة العرض", "حالة العرض"
    ]
    example_row = [
        "إنشاء", "", "عرض الشتاء المميز", "اذا اشترى العميل X يحصل على Y", "متصفح وتطبيق المتجر", 
        "منتجات مختارة", "2026-08-01 00:00:00", "2026-08-30 23:59:59", "لا", 100, 50, 1, 
        "", "منتج", 1, "1234,5678", "منتج", 1, "91011", "خصم بنسبة", 50, "تسوق الآن واستمتع!", "نشط"
    ]
    wb = Workbook()
    ws = wb.active
    ws.title = "Salla Offers Template"
    ws.append(headers)
    ws.append(example_row)
    style_excel_file(ws, is_template=True)
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()

def export_offers_to_excel(offers_list: List[Dict]) -> bytes:
    try:
        from openpyxl import Workbook
        headers = [
            "الإجراء", "معرف العرض", "اسم العرض", "نوع العرض", "المنصة", "تطبيق على", "تاريخ البدء", "تاريخ الانتهاء", 
            "تطبيق مع كوبون", "الحد الأقصى للخصم", "الحد الأدنى للشراء", "الحد الأدنى للكمية", 
            "مجموعات العملاء", "نوع شراء X", "كمية شراء X", "عناصر شراء X (IDs)", 
            "نوع عرض Y", "كمية عرض Y", "عناصر عرض Y (IDs)", "نوع الخصم", "قيمة الخصم", 
            "رسالة العرض", "حالة العرض"
        ]
        wb = Workbook()
        ws = wb.active
        ws.title = "Salla Offers"
        ws.append(headers)

        for o in offers_list:
            buy = o.get('buy', {})
            get = o.get('get', {})
            
            b_type = buy.get('type', 'product')
            if isinstance(b_type, dict): b_type = b_type.get('id', 'product')
            buy_type_ar = {"product": "منتج", "category": "تصنيف", "brand": "ماركة"}.get(b_type, "منتج")
            
            buy_elems = []
            if b_type == 'product': buy_elems = [str(p.get('id', p) if isinstance(p, dict) else p) for p in buy.get('products', [])]
            elif b_type == 'category': buy_elems = [str(c.get('id', c) if isinstance(c, dict) else c) for c in buy.get('categories', [])]
            elif b_type == 'brand': buy_elems = [str(b.get('id', b) if isinstance(b, dict) else b) for b in buy.get('brands', [])]
            
            g_type = get.get('type', 'product')
            if isinstance(g_type, dict): g_type = g_type.get('id', 'product')
            get_type_ar = {"product": "منتج", "category": "تصنيف", "brand": "ماركة"}.get(g_type, "منتج")
            
            get_elems = []
            if g_type == 'product': get_elems = [str(p.get('id', p) if isinstance(p, dict) else p) for p in get.get('products', [])]
            elif g_type == 'category': get_elems = [str(c.get('id', c) if isinstance(c, dict) else c) for c in get.get('categories', [])]
            elif g_type == 'brand': get_elems = [str(b.get('id', b) if isinstance(b, dict) else b) for b in get.get('brands', [])]
            
            disc_type_id = get.get('discount_type', 'percentage')
            if isinstance(disc_type_id, dict): disc_type_id = disc_type_id.get('id', 'percentage')
            disc_type_ar = "منتج مجاني" if disc_type_id == "free-product" else ("خصم بنسبة" if disc_type_id == "percentage" else "مبلغ ثابت")
            
            cust_groups = [str(g.get('id', g) if isinstance(g, dict) else g) for g in o.get('customer_groups', [])]
            o_type_id = o.get('offer_type', '')
            chan_id = o.get('applied_channel', '')
            app_to_id = o.get('applied_to', '')
            
            row = [
                "تحديث", o.get('id', ''), o.get('name', ''), OFFER_TYPES_MAP.get(o_type_id, o_type_id),
                CHANNELS_MAP.get(chan_id, chan_id), APPLIED_TO_MAP.get(app_to_id, app_to_id),
                o.get('start_date', ''), o.get('expiry_date', ''), "نعم" if o.get('applied_with_coupon') else "لا",
                o.get('max_discount_amount', 0), o.get('min_purchase_amount', 0), o.get('min_items_count', 0),
                ",".join(cust_groups), buy_type_ar, buy.get('quantity', 1), ",".join(buy_elems),
                get_type_ar, get.get('quantity', 1), ",".join(get_elems), disc_type_ar,
                get.get('discount_amount', 0), o.get('message', ''), "نشط" if o.get('status') == 'active' else "غير نشط"
            ]
            ws.append(row)
            
        style_excel_file(ws, is_template=False)
        buffer = io.BytesIO()
        wb.save(buffer)
        return buffer.getvalue()
    except Exception as e:
        return b""

def process_excel_import(df) -> dict:
    """معالجة ورفع العروض وإصلاح متطلبات سلة الصارمة (422)"""
    results = {"success": [], "errors": []}
    headers = get_headers()
    if not headers:
        results["errors"].append("فشل في المصادقة.")
        return results

    rev_offer_types = {v: k for k, v in OFFER_TYPES_MAP.items()}
    rev_channels = {v: k for k, v in CHANNELS_MAP.items()}
    rev_applied_to = {v: k for k, v in APPLIED_TO_MAP.items()}
    
    for idx, row in df.iterrows():
        try:
            action = str(row.get('الإجراء', '')).strip()
            offer_id = str(row.get('معرف العرض', '')).strip() if pd.notna(row.get('معرف العرض')) else ''
            
            if action == 'حذف':
                if offer_id and offer_id != 'nan':
                    res = safe_api_request("DELETE", f"{SALLA_API_URL}/{offer_id}", headers)
                    if res is not None: results["success"].append(f"تم حذف العرض بنجاح.")
                    else: results["errors"].append(f"فشل حذف العرض رقم {offer_id}")
                else:
                    results["errors"].append(f"السطر {idx+1}: لا يمكن حذف العرض بدون معرف.")
                continue
                
            o_type = rev_offer_types.get(str(row.get('نوع العرض', '')).strip(), 'buy_x_get_y')
            chan = rev_channels.get(str(row.get('المنصة', '')).strip(), 'browser')
            app_to = rev_applied_to.get(str(row.get('تطبيق على', '')).strip(), 'all')
            with_coupon = str(row.get('تطبيق مع كوبون', '')).strip() == 'نعم'
            
            b_type = {"منتج": "product", "تصنيف": "category", "ماركة": "brand"}.get(str(row.get('نوع شراء X', '')).strip(), "product")
            b_elems_raw = str(row.get('عناصر شراء X (IDs)', '')).strip()
            b_elems = [int(i.strip()) for i in b_elems_raw.split(',')] if b_elems_raw and b_elems_raw != 'nan' else []
            
            g_type = {"منتج": "product", "تصنيف": "category", "ماركة": "brand"}.get(str(row.get('نوع عرض Y', '')).strip(), "product")
            g_elems_raw = str(row.get('عناصر عرض Y (IDs)', '')).strip()
            g_elems = [int(i.strip()) for i in g_elems_raw.split(',')] if g_elems_raw and g_elems_raw != 'nan' else []
            
            disc_type_ar = str(row.get('نوع الخصم', '')).strip()
            disc_type = "free-product" if disc_type_ar == "منتج مجاني" else ("percentage" if disc_type_ar == "خصم بنسبة" else "fixed_amount")
            
            # ✅ إصلاح خطأ 422: منتج مجاني يجب أن يرسل له الخصم 100 إجبارياً
            if disc_type == "free-product":
                discount_amount = 100.0
            else:
                discount_amount = float(row.get('قيمة الخصم', 0) or 0)
            
            cg_raw = str(row.get('مجموعات العملاء', '')).strip()
            c_groups = [int(g.strip()) for g in cg_raw.split(',')] if cg_raw and cg_raw != 'nan' else []
            status = "active" if str(row.get('حالة العرض', '')).strip() == "نشط" else "inactive"
            
            payload = {
                "name": str(row.get('اسم العرض', 'عرض')), 
                "offer_type": o_type, 
                "applied_channel": chan,
                "applied_to": app_to, 
                "start_date": str(row.get('تاريخ البدء', '')).strip(), 
                "expiry_date": str(row.get('تاريخ الانتهاء', '')).strip(),
                "status": status, 
                "applied_with_coupon": with_coupon, 
                "max_discount_amount": float(row.get('الحد الأقصى للخصم', 0) or 0),
                "min_purchase_amount": float(row.get('الحد الأدنى للشراء', 0) or 0), 
                "min_items_count": int(row.get('الحد الأدنى للكمية', 0) or 0),
                "message": str(row.get('رسالة العرض', '')).strip(),
                "buy": {"type": b_type, "quantity": int(row.get('كمية شراء X', 1) or 1)},
                "get": {
                    "type": g_type, 
                    "quantity": int(row.get('كمية عرض Y', 1) or 1), 
                    "discount_type": disc_type, 
                    "discount_amount": discount_amount
                }
            }
            if c_groups: payload["customer_groups"] = c_groups
            if b_type == 'product' and b_elems: payload["buy"]["products"] = b_elems
            elif b_type == 'category' and b_elems: payload["buy"]["categories"] = b_elems
            elif b_type == 'brand' and b_elems: payload["buy"]["brands"] = b_elems
            
            if g_type == 'product' and g_elems: payload["get"]["products"] = g_elems
            elif g_type == 'category' and g_elems: payload["get"]["categories"] = g_elems
            elif g_type == 'brand' and g_elems: payload["get"]["brands"] = g_elems
            
            if pd.isna(payload['message']) or payload['message'] == 'nan': payload['message'] = ''
            
            if action == 'تحديث' and offer_id and offer_id != 'nan':
                res = safe_api_request("PUT", f"{SALLA_API_URL}/{offer_id}", headers, json=payload)
                if res: results["success"].append(f"تم تحديث العرض: {payload['name']}")
                else: results["errors"].append(f"فشل تحديث العرض: {payload['name']}")
            elif action == 'إنشاء':
                res = safe_api_request("POST", SALLA_API_URL, headers, json=payload)
                if res: results["success"].append(f"تم إنشاء العرض: {payload['name']}")
                else: results["errors"].append(f"فشل إنشاء العرض: {payload['name']}")
        except Exception as e:
            results["errors"].append(f"خطأ في الصف {idx+1}: {str(e)}")
    return results

# ==========================================
# 📦 دوال المنتجات والصور والضرائب
# ==========================================

def update_product_status(product_id: int, status: str) -> bool:
    headers = get_headers()
    url = f"https://api.salla.dev/admin/v2/products/{product_id}/status"
    res = safe_api_request("POST", url, headers, json={"status": status})
    return res is not None

def export_products_to_excel(products, po_map=None):
    """تصدير المنتجات إلى ملف Excel منسق واحترافي شامل عمود الماركة"""
    if po_map is None:
        po_map = {}
        
    rows = []
    for p in products:
        p_id = str(p.get('id', ''))
        
        # 🏷️ استخراج اسم الماركة بذكاء
        brand_data = p.get('brand')
        if isinstance(brand_data, dict):
            brand_name = brand_data.get('name') or "بدون ماركة"
        elif isinstance(brand_data, str) and brand_data.strip():
            brand_name = brand_data.strip()
        else:
            brand_name = "بدون ماركة"

        # استخراج التصنيفات
        cats = p.get('categories', [])
        cat_names = [c.get('name', '') for c in cats if isinstance(c, dict)] if isinstance(cats, list) else []
        cat_str = " | ".join(filter(None, cat_names)) if cat_names else "غير مصنف"

        # الأسعار
        price_val = get_flat_price(p.get('price', 0))
        reg_val = get_flat_price(p.get('regular_price', 0))
        sale_val = get_flat_price(p.get('sale_price', 0))
        base_price = reg_val if reg_val > 0 else price_val
        has_disc = (sale_val > 0 and sale_val < base_price)
        display_sale = sale_val if has_disc else "-"
        
        # العناوين الترويجية
        promo = p.get('promotion', {})
        promo_title = p.get('promotion_title') or (promo.get('title') if isinstance(promo, dict) else '') or "-"
        sub_title = p.get('promotion_subtitle') or (promo.get('sub_title') if isinstance(promo, dict) else '') or "-"

        # العروض المشمول بها
        p_offers = po_map.get(p_id, [])
        offers_str = " | ".join([o.get('name', '') for o in p_offers]) if p_offers else "لا يوجد"

        rows.append({
            "معرف المنتج (ID)": p_id,
            "رمز الصنف (SKU)": str(p.get('sku', '')).replace('.0', ''),
            "اسم المنتج": p.get('name', 'بدون اسم'),
            "الماركة": brand_name,  # ✅ عمود الماركة الجديد
            "التصنيفات": cat_str,
            "النوع": "مجموعة منتجات" if p.get('type') == 'group_products' else "منتج فردي",
            "الحالة": "معروض" if p.get('status') == 'sale' else "مخفي",
            "السعر الأساسي": base_price,
            "السعر المخفض": display_sale,
            "تاريخ بداية التخفيض": p.get('sale_start') or "-",
            "تاريخ نهاية التخفيض": p.get('sale_end') or "-",
            "العنوان الترويجي": promo_title,
            "العنوان الفرعي": sub_title,
            "المخزون الإجمالي": p.get('quantity', 0),
            "الكمية المباعة": p.get('sold_quantity', 0),
            "خاضع للضريبة": "نعم" if p.get('with_tax', True) else "معفى",
            "العروض المشمول بها": offers_str,
            "رابط المنتج": p.get('url', '-')
        })

    # بناء وتنسيق الإكسيل
    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "المنتجات"
    ws.sheet_view.rightToLeft = True

    headers = list(df.columns)
    ws.append(headers)
    for row in df.itertuples(index=False, name=None):
        ws.append(row)

    # التنسيق الجمالي
    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    header_font = Font(color="00EBCF", bold=True, size=11)
    center_align = Alignment(horizontal="center", vertical="center")

    for col in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center_align
        ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = 20

    ws.auto_filter.ref = f"A1:{openpyxl.utils.get_column_letter(len(headers))}{ws.max_row}"
    wb.save(buf)
    return buf.getvalue()

def fill_salla_template(products: List[Dict], template_path: str = "Salla_Products_Template.xlsx") -> bytes:
    try:
        import os
        import openpyxl
        import io
        if not os.path.exists(template_path): return b""
        wb = openpyxl.load_workbook(template_path)
        ws = wb["Salla Products Template Sheet"]
        if ws.max_row >= 3: ws.delete_rows(3, ws.max_row - 2)
        start_row = 3 
        for i, p in enumerate(products):
            current_row = start_row + i
            price = get_flat_price(p.get('price', 0))
            sale_price = get_flat_price(p.get('sale_price', 0))
            promo_obj = p.get('promotion', {})
            promo_title = p.get('promotion_title') or (promo_obj.get('title') if isinstance(promo_obj, dict) else '')
            sale_start = p.get('sale_start') or (p.get('sale_price', {}).get('start_at') if isinstance(p.get('sale_price'), dict) else None)
            sale_end = p.get('sale_end') or (p.get('sale_price', {}).get('expired_at') if isinstance(p.get('sale_price'), dict) else None)
            if sale_start and isinstance(sale_start, str): sale_start = sale_start[:10]
            if sale_end and isinstance(sale_end, str): sale_end = sale_end[:10]
            p_id = p.get('id')
            ws.cell(row=current_row, column=1).value = p_id if p_id else None
            ws.cell(row=current_row, column=2).value = 'منتج'
            ws.cell(row=current_row, column=3).value = p.get('name') or 'بدون اسم'
            ws.cell(row=current_row, column=7).value = 'منتج جاهز'
            ws.cell(row=current_row, column=8).value = price if price > 0 else 0
            ws.cell(row=current_row, column=10).value = 'نعم'
            p_sku = p.get('sku')
            ws.cell(row=current_row, column=11).value = p_sku if p_sku else None
            ws.cell(row=current_row, column=13).value = sale_price if sale_price > 0 else None
            ws.cell(row=current_row, column=14).value = sale_start if sale_start else None
            ws.cell(row=current_row, column=15).value = sale_end if sale_end else None
            ws.cell(row=current_row, column=19).value = 1
            ws.cell(row=current_row, column=20).value = 'kg'
            ws.cell(row=current_row, column=21).value = 'متاح' if p.get('status', 'sale') == 'sale' else 'مخفي'
            ws.cell(row=current_row, column=23).value = promo_title if promo_title else None
            ws.cell(row=current_row, column=29).value = 'نعم' if p.get('with_tax', True) else 'لا'
            if not p.get('with_tax', True): ws.cell(row=current_row, column=30).value = p.get('tax_exemption_cause') or 'الأدوية والمعدات الطبية'
            else: ws.cell(row=current_row, column=30).value = None
        output = io.BytesIO()
        wb.save(output)
        return output.getvalue()
    except Exception as e: return b""

def attach_product_image_api(product_id: int, image_bytes: bytes=None, filename: str=None, image_url: str=None) -> bool:
    headers = get_headers()
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
    except: return False

def update_product_promotions_secure(product_id: int, new_promo: str, new_sub: str, headers: dict) -> bool:
    current_res = safe_api_request("GET", f"https://api.salla.dev/admin/v2/products/{product_id}", headers)
    if not current_res or not current_res.get('data'): return False
    p_data = current_res['data']
    price_val = get_flat_price(p_data.get('price', 0))
    sale_val = get_flat_price(p_data.get('sale_price', 0))
    regular_val = get_flat_price(p_data.get('regular_price', 0))
    base_price = regular_val if regular_val > 0 else price_val
    
    payload = {"name": p_data.get('name'), "price": base_price, "status": p_data.get('status', 'sale')}
    if new_promo is not None: payload["promotion_title"] = new_promo
    if new_sub is not None: payload["promotion_subtitle"] = new_sub; payload["subtitle"] = new_sub
    if sale_val > 0: payload['sale_price'] = sale_val
    
    res = safe_api_request("PUT", f"https://api.salla.dev/admin/v2/products/{product_id}", headers, json=payload)
    return res is not None

def update_product_tax_secure(product_id: int, with_tax: bool, tax_cause: str, headers: dict) -> bool:
    current_res = safe_api_request("GET", f"https://api.salla.dev/admin/v2/products/{product_id}", headers)
    if not current_res or not current_res.get('data'): return False
    p_data = current_res['data']
    base_price = get_flat_price(p_data.get('regular_price', 0)) or get_flat_price(p_data.get('price', 0))
    payload = {"name": p_data.get('name'), "price": base_price, "with_tax": with_tax}
    sale_val = get_flat_price(p_data.get('sale_price', 0))
    if sale_val > 0: payload['sale_price'] = sale_val
    if not with_tax and tax_cause: payload["tax_exemption_cause"] = tax_cause
    res = safe_api_request("PUT", f"https://api.salla.dev/admin/v2/products/{product_id}", headers, json=payload)
    return res is not None

def get_branches_list() -> List[Dict]:
    headers = get_headers()
    res = safe_api_request("GET", "https://api.salla.dev/admin/v2/branches", headers)
    return res.get("data", []) if res else []

def generate_quantities_template() -> bytes:
    from openpyxl import Workbook
    from openpyxl.worksheet.datavalidation import DataValidation
    output = io.BytesIO()
    wb = Workbook()
    ws = wb.active
    ws.title = "تحديث الكميات"
    ws.append(["💡 إرشادات: ادخل رقم الـمنتج، ومعرف الفرع، والكمية، ثم اختر نوع العملية."])
    ws.merge_cells('A1:D1')
    ws.row_dimensions[1].height = 24
    ws.append(["Product_SKU", "Branch_ID", "Quantity", "Mode"])
    style_excel_file(ws, is_template=True, header_color="00EBCF")
    dv_mode = DataValidation(type="list", formula1='"increment,decrement,overwrite"', allow_blank=False)
    ws.add_data_validation(dv_mode); dv_mode.add("D3:D1000")
    wb.save(output)
    return output.getvalue()

def process_quantities_import(df: pd.DataFrame) -> Dict:
    results = {"success": [], "errors": []}
    headers = get_headers()
    quantities_payload = []
    for idx, row in df.iterrows():
        if row.isna().all() or str(row.iloc[0]).strip().startswith("💡"): continue
        sku = str(row.get('Product_SKU', '')).strip()
        branch_id = row.get('Branch_ID')
        quantity = int(safe_float(row.get('Quantity', 0)))
        mode = str(row.get('Mode', 'increment')).strip()
        if sku and pd.notna(branch_id):
            quantities_payload.append({"identifer": sku, "identifer_type": "sku", "branch_id": int(float(branch_id)), "quantity": quantity, "mode": mode})
            
    if quantities_payload:
        res = safe_api_request("POST", "https://api.salla.dev/admin/v2/products/quantities/bulk", headers, json={"products": quantities_payload})
        if res: results["success"].append(f"✅ تم تحديث كميات {len(quantities_payload)} سجل بنجاح!")
        else: results["errors"].append("❌ فشل إرسال طلب التحديث الجماعي.")
    return results

def delete_product(product_id: int) -> bool:
    headers = get_headers()
    res = safe_api_request("DELETE", f"https://api.salla.dev/admin/v2/products/{product_id}", headers)
    return res is not None

def update_product_price(product_id: int, new_price: float) -> bool:
    headers = get_headers()
    current_res = safe_api_request("GET", f"https://api.salla.dev/admin/v2/products/{product_id}", headers)
    if not current_res or not current_res.get('data'): return False
    p_data = current_res['data']
    payload = {"name": p_data.get('name'), "price": new_price, "status": p_data.get('status', 'sale')}
    sale_price = get_flat_price(p_data.get('sale_price', 0))
    if sale_price > 0 and sale_price < new_price: payload['sale_price'] = sale_price
    elif sale_price >= new_price: payload['sale_price'] = None
    res = safe_api_request("PUT", f"https://api.salla.dev/admin/v2/products/{product_id}", headers, json=payload)
    return res is not None

def update_product_sale_price(product_id: int, sale_price: float, sale_start: str = None, sale_end: str = None) -> bool:
    headers = get_headers()
    current_res = safe_api_request("GET", f"https://api.salla.dev/admin/v2/products/{product_id}", headers)
    if not current_res or not current_res.get('data'): return False
    
    p_data = current_res['data']
    
    # ✅ الإصلاح الجذري: استخراج السعر الأصلي الحقيقي وتجاهل السعر المتأثر بالتخفيض السابق
    price_val = get_flat_price(p_data.get('price', 0))
    regular_val = get_flat_price(p_data.get('regular_price', 0))
    base_price = regular_val if regular_val > 0 else price_val
    
    # التحقق المنطقي قبل الإرسال لمنع أخطاء 422 من سلة
    if sale_price > 0 and sale_price >= base_price:
        st.error(f"⚠️ السعر المخفض المطلوب ({sale_price}) يجب أن يكون أقل من السعر الأصلي ({base_price})")
        return False
    
    # إرسال السعر الأصلي الحقيقي في الـ Payload لضمان عدم تخريبه
    payload = {"name": p_data.get('name'), "price": base_price, "status": p_data.get('status', 'sale')}
    
    if sale_price > 0:
        payload['sale_price'] = sale_price
        if sale_start: payload['sale_start'] = sale_start
        if sale_end: payload['sale_end'] = sale_end
    else:
        payload['sale_price'] = None # مسح السعر المخفض
        
    res = safe_api_request("PUT", f"https://api.salla.dev/admin/v2/products/{product_id}", headers, json=payload)
    return res is not None

# ==========================================
# 📦 إدارة المجموعات (معالجة خطأ 422 للكميات)
# ==========================================

def get_product_details(product_id: int) -> Optional[Dict]:
    headers = get_headers()
    res = safe_api_request("GET", f"https://api.salla.dev/admin/v2/products/{product_id}", headers)
    return res['data'] if res and res.get('data') else None

def get_group_products(product_id: int) -> List[Dict]:
    headers = get_headers()
    product = get_product_details(product_id)
    if not product or product.get('type') != 'group_products': return []
    
    group_products = []
    if product.get('consisted_products'):
        for item in product['consisted_products']:
            group_products.append({
                'id': item.get('id'), 'name': item.get('name', 'بدون اسم'), 'sku': item.get('sku', 'لا يوجد'),
                'price': get_flat_price(item.get('price', 0)), 'bundle_quantity': item.get('quantity_in_group', 1),
                'stock_quantity': item.get('quantity', 0), 'status': item.get('status', 'sale'),
                'image': item.get('thumbnail') or item.get('main_image'), 'url': item.get('url'),
                'with_tax': item.get('with_tax', True)
            })
    return group_products

def _get_clean_grouped_items(parent_data: dict) -> list:
    """مصفاة ذكية تستخرج العناصر بصيغة grouped_items النظيفة التي تقبلها سلة في طلبات PUT لمنع تخريب المخزون"""
    clean_items = []
    if parent_data.get('consisted_products'):
        for item in parent_data['consisted_products']:
            p_id = item.get('id')
            qty = item.get('quantity_in_group', 1)
            if p_id: clean_items.append({"product_id": p_id, "quantity": qty})
    elif parent_data.get('grouped_items'):
        for item in parent_data['grouped_items']:
            p_id = item.get('product_id') or item.get('product', {}).get('id')
            qty = item.get('quantity', 1)
            if p_id: clean_items.append({"product_id": p_id, "quantity": qty})
    elif parent_data.get('skus'):
        for item in parent_data['skus']:
            p_id = item.get('id')
            qty = item.get('quantity', 1)
            if p_id: clean_items.append({"product_id": p_id, "quantity": qty})
    return clean_items

def update_group_product_quantity(parent_product_id: int, child_product_id: int, new_quantity: int) -> bool:
    """✅ دالة جراحية لمنع خطأ 422 عند تحديث الكميات في مجموعة المنتجات"""
    headers = get_headers()
    parent = get_product_details(parent_product_id)
    if not parent: return False

    clean_items = _get_clean_grouped_items(parent)
    updated = False

    for item in clean_items:
        if str(item['product_id']) == str(child_product_id):
            item['quantity'] = new_quantity
            updated = True
            break

    if not updated: return False

    payload = {
        "name": parent.get('name'),
        "type": "group_products",
        "grouped_items": clean_items
    }

    res = safe_api_request("PUT", f"https://api.salla.dev/admin/v2/products/{parent_product_id}", headers, json=payload)
    return res is not None

def remove_product_from_group(parent_product_id: int, child_product_id: int) -> bool:
    headers = get_headers()
    parent = get_product_details(parent_product_id)
    if not parent: return False
    
    clean_items = _get_clean_grouped_items(parent)
    new_items = [item for item in clean_items if str(item['product_id']) != str(child_product_id)]
    
    if len(new_items) == len(clean_items): return False
            
    payload = {
        "name": parent.get('name'),
        "type": "group_products",
        "grouped_items": new_items
    }
    res = safe_api_request("PUT", f"https://api.salla.dev/admin/v2/products/{parent_product_id}", headers, json=payload)
    return res is not None

def add_product_to_group(parent_product_id: int, child_product_id: int) -> bool:
    headers = get_headers()
    parent = get_product_details(parent_product_id)
    if not parent: return False
    
    clean_items = _get_clean_grouped_items(parent)
    for item in clean_items:
        if str(item['product_id']) == str(child_product_id): return False
        
    clean_items.append({"product_id": int(child_product_id), "quantity": 1})
    payload = {
        "name": parent.get('name'),
        "type": "group_products",
        "grouped_items": clean_items
    }
    res = safe_api_request("PUT", f"https://api.salla.dev/admin/v2/products/{parent_product_id}", headers, json=payload)
    return res is not None

# ==========================================
# 👥 دوال العملاء والمجموعات (تم استعادتها)
# ==========================================

def get_customers_list(keyword: str = "") -> Optional[Dict]:
    headers = get_headers()
    if not headers: return None
    url = "https://api.salla.dev/admin/v2/customers"
    params = {"keyword": keyword} if keyword else {}
    return safe_api_request("GET", url, headers, params=params)

def create_customer(customer_data: Dict) -> bool:
    headers = get_headers()
    res = safe_api_request("POST", "https://api.salla.dev/admin/v2/customers", headers, json=customer_data)
    return res is not None

def update_customer_api(customer_id: int, customer_data: Dict) -> bool:
    headers = get_headers()
    res = safe_api_request("PUT", f"https://api.salla.dev/admin/v2/customers/{customer_id}", headers, json=customer_data)
    return res is not None

def delete_customer_api(customer_id: int) -> bool:
    headers = get_headers()
    res = safe_api_request("DELETE", f"https://api.salla.dev/admin/v2/customers/{customer_id}", headers)
    return res is not None

def get_customer_groups_list() -> Optional[Dict]:
    headers = get_headers()
    return safe_api_request("GET", "https://api.salla.dev/admin/v2/customers/groups", headers)

def create_customer_group(group_data: Dict) -> bool:
    headers = get_headers()
    res = safe_api_request("POST", "https://api.salla.dev/admin/v2/customers/groups", headers, json=group_data)
    return res is not None

def update_customer_group_api(group_id: int, group_data: Dict) -> bool:
    headers = get_headers()
    res = safe_api_request("PUT", f"https://api.salla.dev/admin/v2/customers/groups/{group_id}", headers, json=group_data)
    return res is not None

def delete_customer_group_api(group_id: int) -> bool:
    headers = get_headers()
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
    except: return b""

def export_customer_groups_to_excel(groups: List[Dict]) -> bytes:
    try:
        data = [{'معرف المجموعة': g.get('id', ''), 'اسم المجموعة': g.get('name', '')} for g in groups]
        df = pd.DataFrame(data)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
            style_excel_file(writer.sheets['Sheet1'], is_template=False, header_color="0F1C2E")
        return buffer.getvalue()
    except Exception as e: 
        st.error(f"خطأ في التصدير: {e}")
        return b""

def generate_salla_new_products_file(products: List[Dict]) -> bytes:
    try:
        import io
        from openpyxl import Workbook
        from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
        from openpyxl.utils import get_column_letter

        wb = Workbook()
        ws = wb.active
        ws.title = "Salla Products Template Sheet"
        
        row1 = ["بيانات المنتج"] + [""] * 18 + ["الخيارات والبيانات الإضافية"] + [""] * 20
        ws.append(row1)
        
        headers = [
            "النوع ", "أسم المنتج", "تصنيف المنتج", "صورة المنتج", "وصف صورة المنتج",
            "نوع المنتج", "سعر المنتج", "الوصف", "هل يتطلب شحن؟", "رمز المنتج sku",
            "سعر التكلفة", "السعر المخفض", "تاريخ بداية التخفيض", "تاريخ نهاية التخفيض",
            "اقصي كمية لكل عميل", "إخفاء خيار تحديد الكمية", "اضافة صورة عند الطلب",
            "الوزن", "وحدة الوزن", "الماركة", "العنوان الترويجي", "تثبيت المنتج",
            "الباركود", "السعرات الحرارية", "MPN", "GTIN", "خاضع للضريبة ؟",
            "سبب عدم الخضوع للضريبة", 
            "[1] الاسم", "[1] النوع", "[1] القيمة", "[1] الصورة / اللون",
            "[2] الاسم", "[2] النوع", "[2] القيمة", "[2] الصورة / اللون",
            "[3] الاسم", "[3] النوع", "[3] القيمة", "[3] الصورة / اللون"
        ]
        
        # صف البيانات الرئيسي
        ws.append(headers)

        for p in products:
            price = get_flat_price(p.get('price', 0))
            is_taxable = p.get('with_tax', True)
            tax_cause = p.get('tax_exemption_cause', '') if not is_taxable else ""
            
            # ✅ تعيين الكميات الافتراضية لتكون 50
            max_qty = p.get('maximum_quantity_per_order')
            if max_qty is None or max_qty == "": max_qty = 50
            else:
                try: max_qty = int(max_qty)
                except: max_qty = 50
                if max_qty < 1: max_qty = 50
                
            max_items = p.get('max_items_per_user')
            if max_items is None or max_items == "": max_items = 50
            else:
                try: max_items = int(max_items)
                except: max_items = 50
                if max_items < 1: max_items = 50
            
            row = [
                "منتج",  # النوع
                p.get('name', 'بدون اسم'),  # أسم المنتج
                "",  # تصنيف المنتج
                "",  # صورة المنتج
                "",  # وصف صورة المنتج
                "منتج جاهز",  # نوع المنتج
                price if price > 0 else 0,  # سعر المنتج
                "",  # الوصف
                "نعم",  # هل يتطلب شحن؟
                p.get('sku', ""),  # رمز المنتج sku
                "",  # سعر التكلفة
                "",  # السعر المخفض
                "",  # تاريخ بداية التخفيض
                "",  # تاريخ نهاية التخفيض
                max_qty,  # اقصي كمية لكل عميل ✅
                "لا",  # إخفاء خيار تحديد الكمية
                "لا",  # اضافة صورة عند الطلب
                1,  # الوزن
                "kg",  # وحدة الوزن
                "",  # الماركة
                p.get('promotion_title', ""),  # العنوان الترويجي
                "لا",  # تثبيت المنتج
                "",  # الباركود
                "",  # السعرات الحرارية
                "",  # MPN
                "",  # GTIN
                "نعم" if is_taxable else "لا",  # خاضع للضريبة ؟
                tax_cause,  # سبب عدم الخضوع للضريبة
                "", "", "", "",  # الخيار 1
                "", "", "", "",  # الخيار 2
                "", "", "", ""   # الخيار 3
            ]
            ws.append(row)

        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=19)
        ws.merge_cells(start_row=1, start_column=20, end_row=1, end_column=40)
        
        elegant_purple = PatternFill(start_color="8B5CF6", end_color="8B5CF6", fill_type="solid")
        dark_slate = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
        
        font_title = Font(name="Segoe UI", size=14, bold=True, color="FFFFFF")
        font_headers = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
        center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
        thin_border = Border(left=Side(style='thin', color='DDDDDD'), right=Side(style='thin', color='DDDDDD'), 
                             top=Side(style='thin', color='DDDDDD'), bottom=Side(style='thin', color='DDDDDD'))
        
        ws.row_dimensions[1].height = 35
        cell_1 = ws.cell(row=1, column=1); cell_1.fill = elegant_purple; cell_1.font = font_title; cell_1.alignment = center_align
        cell_20 = ws.cell(row=1, column=20); cell_20.fill = elegant_purple; cell_20.font = font_title; cell_20.alignment = center_align

        ws.row_dimensions[2].height = 25
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=2, column=col_idx)
            cell.fill = dark_slate; cell.font = font_headers; cell.alignment = center_align; cell.border = thin_border
            ws.column_dimensions[get_column_letter(col_idx)].width = 22

        output = io.BytesIO()
        wb.save(output)
        return output.getvalue()
    except Exception as e:
        return b""
# ==========================================
# 🏷️ دوال التحكم الجماعي في العناوين والأسعار المخفضة (بدون ID)
# ==========================================

def generate_promotions_template() -> bytes:
    from openpyxl import Workbook
    from openpyxl.worksheet.datavalidation import DataValidation
    from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "تحديث العناوين والأسعار"

    # إضافة صف الإرشادات
    ws.append(["💡 إرشادات: ادخل رقم الـ SKU، العناوين الجديدة، السعر المخفض وتاريخ الانتهاء، ثم اختر الإجراء المطلوب."])
    ws.merge_cells('A1:F1')
    ws.row_dimensions[1].height = 24

    # ✅ العناوين الجديدة مع عمود تاريخ الانتهاء
    headers = ["SKU (رقم المنتج)", "العنوان الترويجي", "العنوان الفرعي", "السعر المخفض", "تاريخ انتهاء التخفيض", "الإجراء المطلوب"]
    ws.append(headers)

    # التنسيق الاحترافي
    header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, name="Cairo", size=12)
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin_border = Border(left=Side(style='thin', color='DDDDDD'), right=Side(style='thin', color='DDDDDD'), 
                         top=Side(style='thin', color='DDDDDD'), bottom=Side(style='thin', color='DDDDDD'))

    for col in range(1, len(headers) + 1):
        cell = ws.cell(row=2, column=col)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center_align
        cell.border = thin_border
        ws.column_dimensions[get_column_letter(col)].width = 25

    # ✅ قائمة منسدلة للإجراءات (تم إضافة: تحديث تاريخ الانتهاء) في العمود السادس (F)
    dv = DataValidation(type="list", formula1='"تحديث,تحديث السعر المخفض,تحديث تاريخ الانتهاء,مسح الترويجي,مسح الفرعي,مسح الكل"', allow_blank=False)
    ws.add_data_validation(dv)
    dv.add("F3:F1000")

    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()

# 1. تحديث دالة المعالجة الجماعية لدعم شريط التقدم
def process_promotions_bulk(df: pd.DataFrame, products_list: List[Dict], headers: Dict[str, str], progress_callback=None) -> Dict:
    results = {"success": [], "errors": []}
    
    sku_to_product = {}
    for p in products_list:
        if p.get('sku'):
            clean_sku = str(p.get('sku')).strip()
            if clean_sku.endswith('.0'): clean_sku = clean_sku[:-2]
            sku_to_product[clean_sku] = p
            
    # تصفية الصفوف الصالحة لحساب النسبة الدقيقة
    valid_rows = [r for _, r in df.iterrows() if not r.isna().all() and not str(r.iloc[0]).strip().startswith("💡")]
    total_valid = len(valid_rows)

    for idx, row in enumerate(valid_rows):
        sku_raw = str(row.get('SKU (رقم المنتج)', '')).strip()
        if sku_raw.endswith('.0'): sku_raw = sku_raw[:-2]
        if not sku_raw or sku_raw == 'nan': continue
        
        # استدعاء دالة تحديث شريط التقدم
        if progress_callback and total_valid > 0:
            try:
                progress_callback(idx + 1, total_valid, sku_raw)
            except Exception:
                pass

        p = sku_to_product.get(sku_raw)
        if not p:
            results["errors"].append(f"السطر {idx+2}: لم يتم العثور على منتج بـ SKU ({sku_raw})")
            continue
            
        p_id = p['id']
        action = str(row.get('الإجراء المطلوب', 'تحديث')).strip()
        promo_val = str(row.get('العنوان الترويجي', '')).strip()
        sub_val = str(row.get('العنوان الفرعي', '')).strip()
        sale_price_val = str(row.get('السعر المخفض', '')).strip()
        
        sale_end_raw = row.get('تاريخ انتهاء التخفيض', '')
        sale_end_val = ""
        if pd.notna(sale_end_raw) and str(sale_end_raw).strip() not in ['', 'nan']:
            try:
                parsed_date = pd.to_datetime(sale_end_raw)
                if parsed_date.hour == 0 and parsed_date.minute == 0:
                    sale_end_val = parsed_date.strftime('%Y-%m-%d 23:59:59')
                else:
                    sale_end_val = parsed_date.strftime('%Y-%m-%d %H:%M:%S')
            except:
                sale_end_val = str(sale_end_raw).strip()
        
        if promo_val == 'nan': promo_val = ""
        if sub_val == 'nan': sub_val = ""
        if sale_price_val == 'nan': sale_price_val = ""
        
        current_promo = p.get('promotion_title', '') or (p.get('promotion', {}).get('title', '') if isinstance(p.get('promotion'), dict) else '')
        current_sub = p.get('promotion_subtitle', '') or (p.get('promotion', {}).get('sub_title', '') if isinstance(p.get('promotion'), dict) else '')
        current_sale = get_flat_price(p.get('sale_price', 0))
        current_sale_end = str(p.get('sale_end', '')) if p.get('sale_end') else ""
        
        new_promo = current_promo
        new_sub = current_sub
        new_sale = current_sale
        new_sale_end = current_sale_end
        
        if action == 'تحديث':
            new_promo = promo_val
            new_sub = sub_val
            new_sale = float(sale_price_val) if sale_price_val != "" else 0.0
            new_sale_end = sale_end_val
        elif action == 'تحديث السعر المخفض':
            new_sale = float(sale_price_val) if sale_price_val != "" else 0.0
            new_sale_end = sale_end_val
        elif action == 'تحديث تاريخ الانتهاء':
            new_sale_end = sale_end_val
        elif action == 'مسح الترويجي':
            new_promo = ""
            if sub_val: new_sub = sub_val
            if sale_price_val: new_sale = float(sale_price_val)
            if sale_end_val != "": new_sale_end = sale_end_val
        elif action == 'مسح الفرعي':
            new_sub = ""
            if promo_val: new_promo = promo_val
            if sale_price_val: new_sale = float(sale_price_val)
            if sale_end_val != "": new_sale_end = sale_end_val
        elif action == 'مسح الكل':
            new_promo = ""; new_sub = ""; new_sale = 0.0; new_sale_end = ""
        
        base_price = get_flat_price(p.get('regular_price', 0)) or get_flat_price(p.get('price', 0))
        if new_sale > 0 and new_sale >= base_price:
            results["errors"].append(f"السطر {idx+2}: السعر المخفض ({new_sale}) أكبر من الأصلي ({base_price}) للمنتج {sku_raw}")
            continue
            
        payload = {
            "name": p.get('name'), "price": base_price, "status": p.get('status', 'sale'),
            "promotion_title": new_promo, "promotion_subtitle": new_sub, "subtitle": new_sub
        }
        if new_sale > 0:
            payload['sale_price'] = new_sale
            payload['sale_end'] = new_sale_end if new_sale_end else None
        else:
            payload['sale_price'] = None
            payload['sale_end'] = None
            
        res = safe_api_request("PUT", f"https://api.salla.dev/admin/v2/products/{p_id}", headers, json=payload)
        if res: results["success"].append(f"تم تنفيذ ({action}) للمنتج {sku_raw} بنجاح.")
        else: results["errors"].append(f"فشل تنفيذ ({action}) للمنتج {sku_raw}.")
        time.sleep(0.3)
            
    return results


# 2. تحديث محرك الجدولة ليقوم بتسجيل نسبة الإنجاز
def background_scheduler_worker():
    """محرك فحص المهام المجدولة مع تسجيل شريط التقدم لحظياً"""
    while True:
        try:
            schedules = load_schedules()
            saudi_now = datetime.now(timezone(timedelta(hours=3))).replace(tzinfo=None)
            modified = False

            for task in schedules:
                if task.get("status") == "pending":
                    run_time = datetime.strptime(task["run_at"], "%Y-%m-%d %H:%M")
                    if saudi_now >= run_time:
                        file_path = os.path.join(SCHEDULE_DIR, task["filename"])
                        meta_path = os.path.join(SCHEDULE_DIR, task["filename"] + ".meta.json")
                        
                        if os.path.exists(file_path):
                            # تغيير الحالة إلى "جاري التنفيذ"
                            task["status"] = "in_progress"
                            task["progress"] = 0
                            task["current_sku"] = "بدء المعالجة"
                            save_schedules(schedules)
                            
                            df_promo = pd.read_excel(file_path)
                            headers = get_headers()
                            
                            cached_products = []
                            if os.path.exists(meta_path):
                                try:
                                    with open(meta_path, "r", encoding="utf-8") as mf:
                                        cached_products = json.load(mf)
                                except Exception:
                                    cached_products = []

                            def update_task_progress(cur, total, sku):
                                task["progress"] = int((cur / total) * 100)
                                task["processed_count"] = cur
                                task["total_count"] = total
                                task["current_sku"] = str(sku)
                                save_schedules(schedules)
                                    
                            process_promotions_bulk(df_promo, cached_products, headers, progress_callback=update_task_progress)
                            task["status"] = "completed"
                            task["progress"] = 100
                            task["executed_at"] = saudi_now.strftime("%Y-%m-%d %I:%M %p")
                        else:
                            task["status"] = "failed (file missing)"
                        modified = True

            if modified:
                save_schedules(schedules)
        except Exception as e:
            print(f"Error in scheduler worker: {e}")

        time.sleep(20)

def export_featured_group_to_excel(group_products: List[Dict], po_map: Dict) -> bytes:
    """تصدير منتجات المجموعة المميزة إلى ملف Excel احترافي ومنسق (محدث بالعناوين والمخزون والحالة)"""
    try:
        import io
        from openpyxl import Workbook
        from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
        from openpyxl.utils import get_column_letter

        wb = Workbook()
        ws = wb.active
        ws.title = "بيانات المجموعة"

        # ✅ إضافة العناوين الجديدة المطلوبة
        headers = [
            "SKU", "اسم المنتج", "سعر المنتج", "السعر المخفض", 
            "تاريخ انتهاء التخفيض", "العنوان الترويجي", "العنوان الفرعي", 
            "المخزون", "الحالة (متاح/مخفي)",
            "مشمول في عرض خاص؟", "اسم العرض الخاص"
        ]
        ws.append(headers)

        for p in group_products:
            pid_str = str(p.get('id', ''))
            price = get_flat_price(p.get('price', 0))
            regular_price = get_flat_price(p.get('regular_price', 0))
            base_price = regular_price if regular_price > 0 else price
            sale_price = get_flat_price(p.get('sale_price', 0))

            # استخراج العناوين الترويجية والفرعية
            promo_obj = p.get('promotion', {})
            promo_title = p.get('promotion_title') or (promo_obj.get('title') if isinstance(promo_obj, dict) else '') or ""
            promo_sub = p.get('promotion_subtitle') or (promo_obj.get('sub_title') if isinstance(promo_obj, dict) else '') or ""

            # ✅ استخراج المخزون والحالة
            stock = p.get('quantity', 0)
            status = "متاح" if p.get('status', 'sale') == 'sale' else "مخفي"

            # فحص العروض المربوطة
            offers = po_map.get(pid_str, [])
            in_offer = "نعم" if offers else "لا"
            offer_names = " ، ".join([o['name'] for o in offers]) if offers else "لا يوجد"

            ws.append([
                p.get('sku', 'لا يوجد'),
                p.get('name', 'بدون اسم'),
                base_price,
                sale_price if sale_price > 0 else "بدون تخفيض",
                p.get('sale_end', 'بدون تاريخ') if sale_price > 0 else "-",
                promo_title,
                promo_sub,
                stock,        # إدراج المخزون
                status,       # إدراج الحالة
                in_offer,
                offer_names
            ])

        # التنسيق الاحترافي
        elegant_purple = PatternFill(start_color="8B5CF6", end_color="8B5CF6", fill_type="solid") # لون مميز للمجموعات
        header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
        center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
        thin_border = Border(left=Side(style='thin', color='DDDDDD'), right=Side(style='thin', color='DDDDDD'),
                             top=Side(style='thin', color='DDDDDD'), bottom=Side(style='thin', color='DDDDDD'))

        ws.row_dimensions[1].height = 25
        for col in range(1, len(headers) + 1):
            cell = ws.cell(row=1, column=col)
            cell.fill = elegant_purple
            cell.font = header_font
            cell.alignment = center_align
            cell.border = thin_border
            ws.column_dimensions[get_column_letter(col)].width = 22

        ws.column_dimensions['B'].width = 40 # توسيع عمود الاسم
        ws.column_dimensions['K'].width = 35 # توسيع عمود اسم العرض (أصبح العمود K بدل I لزيادة الأعمدة)
        
        # تفعيل الفلترة التلقائية
        ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{ws.max_row}"

        output = io.BytesIO()
        wb.save(output)
        return output.getvalue()
    except Exception as e:
        import streamlit as st
        st.error(f"خطأ في إنشاء ملف التصدير: {e}")
        return b""

SCHEDULE_DIR = "scheduled_uploads"
SCHEDULE_FILE = "schedules.json"

os.makedirs(SCHEDULE_DIR, exist_ok=True)

def load_schedules():
    if not os.path.exists(SCHEDULE_FILE):
        return []
    try:
        with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_schedules(schedules):
    with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
        json.dump(schedules, f, ensure_ascii=False, indent=2)

# بدء تشغيل محرك الجدولة مرة واحدة عند تشغيل السيرفر
def init_background_scheduler():
    """تشغيل خيط الجدولة وربطه بسياق Streamlit بأمان"""
    # التحقق من عدم تشغيل الخيط مسبقاً لمنع التكرار
    for th in threading.enumerate():
        if th.name == "SallaPromoDaemon":
            return
            
    daemon_thread = threading.Thread(
        target=background_scheduler_worker, 
        name="SallaPromoDaemon", 
        daemon=True
    )
    
    # ✅ إضافة سياق التشغيل للثريد لمنع خطأ ScriptRunContext
    try:
        add_script_run_ctx(daemon_thread)
    except Exception as e:
        print(f"Notice: Could not attach script context: {e}")
        
    daemon_thread.start()

# بدء تشغيل الخيط
init_background_scheduler()

# ==========================================
# 🔑 إدارة صلاحية وتحديث Access Token للمتجر
# ==========================================

def check_token_expiry_info(merchant_id=None):
    """
    فحص صلاحية التوكن وحساب الأيام المتبقية لدورة الـ 14 يوماً
    تُرجع: (needs_alert: bool, days_left: float, expiry_date: datetime, last_updated_str: str)
    """
    try:
        store = get_salla_store(merchant_id)
        if not store:
            return False, 14.0, None, ""

        expires_at = int(store.get("expires_at") or 0)
        if not expires_at:
            return True, 0.0, None, ""

        expiry_dt = datetime.fromtimestamp(expires_at, tz=timezone.utc).astimezone()
        days_left = (expires_at - time.time()) / 86400.0
        needs_alert = days_left <= 5.0
        return needs_alert, days_left, expiry_dt, str(store.get("token_updated_at") or "")

    except Exception:
        logger.exception("Error checking Salla token expiry")
        return False, 14.0, None, ""

def update_store_tokens(
    new_access_token: str,
    new_refresh_token: str,
    merchant_id: str,
    expires_at=None,
) -> bool:
    merchant_id = str(merchant_id or "").strip()
    access_token = str(new_access_token or "").strip()
    refresh_token = str(new_refresh_token or "").strip()

    if not merchant_id or not access_token or not refresh_token:
        return False

    try:
        existing = get_salla_store(merchant_id)
        if expires_at is None:
            expires_at = int(time.time()) + 14 * 24 * 60 * 60
        else:
            expires_at = int(expires_at)

        now = datetime.now(timezone.utc).isoformat()
        row = {
            "merchant_id": merchant_id,
            "store_name": (existing or {}).get("store_name") or f"متجر {merchant_id}",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": expires_at,
            "installed_at": (existing or {}).get("installed_at") or now,
            "token_updated_at": now,
        }
        (
            get_supabase_client()
            .table("salla_stores")
            .upsert(row, on_conflict="merchant_id")
            .execute()
        )

        if str(st.session_state.get("merchant_id", "")) == merchant_id:
            st.session_state["access_token"] = access_token
            st.session_state["sync_after_token_save"] = True
        return True

    except Exception:
        logger.exception("Failed to save Salla tokens to Supabase")
        return False
