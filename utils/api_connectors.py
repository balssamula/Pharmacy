import requests
import json
import pandas as pd
import pymysql
from datetime import datetime, timedelta

def fetch_abc_invoices_live() -> pd.DataFrame:
    """قراءة فواتير ABC حياً ومباشرة من قاعدة بيانات Supabase المشتركة"""
    SUPABASE_URL = "https://dvikehqqkfscoozjlysz.supabase.co/rest/v1/abc_invoices?select=*"
    SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImR2aWtlaHFxa2ZzY29vempseXN6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODA5MTQ1MjUsImV4cCI6MjA5NjQ5MDUyNX0.h5Ip3wkp3rgSV6VXCTCCfV_aPba0TRDIBjfBa1q9eK0"
    
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}"
    }
    
    try:
        response = requests.get(SUPABASE_URL, headers=headers, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if not data:
                return pd.DataFrame()
            
            df_cloud = pd.DataFrame(data)
            
            # إعادة ترجمة الأعمدة للعربية ليتوافق مع واجهات المحرك الافتراضية للسيستم
            column_mapping_arabic = {
                'receipt_no': 'رقم الفاتورة',
                'item_no': 'رقم الصنف',
                'product_name': 'اسم الصنف',
                'net_qty': 'Net Sold Qty',
                'sales_date': 'التاريخ',
                'branch_name': 'رقم الصيدلية',
                'username': 'الصيدلي',
                'profile_type': 'نوع البروفايل'
            }
            return df_cloud.rename(columns=column_mapping_arabic)
        else:
            return pd.DataFrame()
    except Exception:
        return pd.DataFrame()


# 🔑 إعدادات تطبيق سلة (Salla Partners Application) المستخرجة من ملفات الـ OpenAPI لديك
SALLA_CLIENT_ID = "8a6c31ed-b841-48ca-85a9-3596e4d60d01"
SALLA_CLIENT_SECRET = "1c9c66a597ec06c7ab9cd89d9d4e9a8bed005e6ee279e35ede14f905170b1ea5"
SALLA_BASE_URL = "https://api.salla.dev/admin/v2/"

def refresh_salla_token(current_refresh_token: str) -> dict:
    """
    تجديد صلاحية الـ Access Token لمنصة سلة تلقائياً قبل انتهائه (كل 24 ساعة).
    بناءً على توثيق ملف الـ OpenAPI (tokenUrl) المرفق في مشروعك.
    """
    token_url = "https://accounts.salla.sa/oauth2/token"
    
    payload = {
        "client_id": SALLA_CLIENT_ID,
        "client_secret": SALLA_CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": current_refresh_token,
        "redirect_uri": "https://app.apidog.com/oauth2-browser-callback.html"
    }
    
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    try:
        response = requests.post(token_url, data=payload, headers=headers, timeout=15.0)
        if response.status_code == 200:
            token_data = response.json()
            print("🔑 تم تجديد مفاتيح الوصول لمنصة سلة (OAuth2) بنجاح تلقائي.")
            # سيعود بـ access_token جديد و refresh_token جديد
            return token_data
        else:
            print(f"❌ فشل تجديد توكن سلة. كود الاستجابة: {response.status_code}")
            return {}
    except Exception as e:
        print(f"❌ خطأ في دالة refresh_salla_token: {e}")
        return {}


def parse_salla_webhook_payload(webhook_json: dict) -> pd.DataFrame:
    """
    تحويل الإشارة الفورية (JSON Payload) المستقبلة من Webhook سلة عند حدوث طلب جديد،
    وتفكيك الأصناف (Order Items) وتحويلها إلى DataFrame يطابق كود المطابقة المحاسبي.
    """
    try:
        # استخراج بيانات الطلب بناءً على المخطط التفصيلي للهيكل المرفق لديك
        order_data = webhook_json.get('data', webhook_json)
        order_number = str(order_data.get('id', ''))
        customer = order_data.get('customer', {})
        customer_name = f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip()
        customer_phone = customer.get('mobile', '')
        
        shipping = order_data.get('shipping', {})
        city = shipping.get('address', {}).get('city', '')
        
        order_status = order_data.get('status', {}).get('name', '')
        order_date = order_data.get('created_at', '')
        total_amount = float(order_data.get('amounts', {}).get('total', {}).get('amount', 0))
        
        # استخراج مصفوفة المنتجات والأصناف داخل الطلب (Items Array)
        items = order_data.get('items', [])
        parsed_items = []
        
        for item in items:
            parsed_items.append({
                "رقم الطلب": order_number,
                "SKU": str(item.get('sku', '')),
                "اسم المنتج": str(item.get('name', '')),
                "الكمية": int(item.get('quantity', 1)),
                "اسم العميل": customer_name,
                "رقم الجوال": customer_phone,
                "المدينة": city,
                "حالة الطلب": order_status,
                "تاريخ الطلب": order_date,
                "إجمالي الطلب": total_amount
            })
            
        if parsed_items:
            df_salla_sync = pd.DataFrame(parsed_items)
            print(f"📦 تم تفكيك وتحويل طلب سلة رقم ({order_number}) بنجاح إلى جدول معالجة.")
            return df_salla_sync
        return pd.DataFrame()
        
    except Exception as e:
        print(f"❌ خطأ أثناء تفكيك وقراءة JSON Webhook سلة: {e}")
        return pd.DataFrame()

def get_salla_special_offers(access_token: str) -> list:
    """جلب قائمة العروض الخاصة من متجر سلة (طبقاً لملف List Special Offers.md)"""
    url = f"{SALLA_BASE_URL}specialoffers"
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    try:
        response = requests.get(url, headers=headers, timeout=15.0)
        if response.status_code == 200:
            return response.json().get('data', [])
        return []
    except Exception as e:
        print(f"Error listing special offers: {e}")
        return []

def create_salla_special_offer(access_token: str, offer_payload: dict) -> bool:
    """إنشاء عرض خاص جديد في المتجر (طبقاً لملف Create Special Offer.md)"""
    url = f"{SALLA_BASE_URL}specialoffers"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    try:
        response = requests.post(url, json=offer_payload, headers=headers, timeout=15.0)
        return response.status_code in [200, 201]
    except Exception as e:
        print(f"Error creating special offer: {e}")
        return False

def change_special_offer_status(access_token: str, offer_id: int, status: str) -> bool:
    """تعديل حالة العرض نشط/غير نشط (طبقاً لملف Change Special Offer Status.md)"""
    url = f"{SALLA_BASE_URL}specialoffers/{offer_id}/status"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    try:
        response = requests.put(url, json={"status": status}, headers=headers, timeout=15.0)
        return response.status_code == 200
    except Exception as e:
        print(f"Error changing offer status: {e}")
        return False

def process_special_offers_excel_sync(uploaded_file, access_token: str):
    """
    قراءة ملف Excel يحتوي على مجموعة عروض وبثها تلقائياً إلى API سلة.
    يتوقع الملف أعمدة: (name, message, offer_type, min_purchase_amount, status)
    """
    try:
        df_offers = pd.read_excel(uploaded_file)
        success_count = 0
        
        for _, row in df_offers.iterrows():
            payload = {
                "name": str(row.get('name', row.get('اسم العميل', ''))),
                "message": str(row.get('message', row.get('الرسالة التسويقية', ''))),
                "offer_type": str(row.get('offer_type', 'buy_x_get_y')),
                "applied_channel": "browser_and_application",
                "min_purchase_amount": int(row.get('min_purchase_amount', 100)),
                "status": str(row.get('status', 'active'))
            }
            # إرسال كل سطر كطلب منفصل لـ API سلة
            if create_salla_special_offer(access_token, payload):
                success_count += 1
                
        return True, f"✅ تم بنجاح معالجة الملف ونشر {success_count} عرض ترويجي على متجرك فوراً!"
    except Exception as e:
        return False, f"❌ خطأ أثناء قراءة ملف عروض الـ Excel: {e}"
