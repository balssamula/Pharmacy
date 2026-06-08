import requests
import json
import pandas as pd
import pymysql
from datetime import datetime, timedelta

def fetch_abc_invoices_live() -> pd.DataFrame:
    """
    [البديل الآلي الحقيقي]: الاتصال المباشر بقاعدة بيانات MySQL لنظام ABC 
    وسحب فواتير اليوم تلقائياً وتحويلها إلى DataFrame جاهز تماماً للمطابقة والفرز.
    """
    # 🔑 إعدادات الاتصال الحقيقية والمستخرجة من ملف ABC.set الخاص بصيدليتك
    host = '10.20.1.15'
    user = 'olamng'
    password = 'ola@abc'
    database = 'abc'
    port = 3306
    ssl_ca_path = 'data/ABC1.pem' # مسار ملف الشهادة الأمنية المرفق لحماية الاتصال
    
    try:
        print(f"🔄 جاري فتح اتصال آمن مباشر بقاعدة بيانات ABC ({host})...")
        
        # إنشاء الاتصال بقاعدة البيانات المحلية 
        connection = pymysql.connect(
            host=host,
            user=user,
            password=password,
            database=database,
            port=port,
            ssl={'ca': ssl_ca_path} if os.path.exists(ssl_ca_path) else None,
            timeout=15
        )
        
        # استعلام جلب فواتير اليوم الحالي تلقائياً بناءً على تاريخ السيرفر
        # ملحوظة هندسية: يتم تعديل اسم الجدول 'sales_invoices' واسم عمود التاريخ 'sales_date' 
        # بناءً على المخطط الداخلي الفعلي لجداول قاعدة بيانات ABC لديك في حال اختلافها.
        query = "SELECT * FROM sales_invoices WHERE DATE(sales_date) = CURDATE()"
        
        # قراءة البيانات المقروءة من MySQL وتحويلها فوراً لـ DataFrame في الذاكرة
        df_raw = pd.read_sql(query, connection)
        connection.close()
        
        if df_raw.empty:
            print("📭 مزامنة ABC: الاتصال ناجح بالسيرفر، ولكن لا توجد فواتير مسجلة اليوم حتى الآن.")
            return pd.DataFrame()
            
        # 🧠 [هندسة التحويل والترجمة]: خريطة مطابقة الجداول وتوحيد مسميات أعمدة الـ MySQL لتطابق محرك التسويات الحالي
        # يتم تعديل الجانب الأيسر (الـ Keys) لتطابق أسماء الأعمدة في جداول MySQL الحقيقية لـ ABC صراحةً
        column_mapping = {
            'OrderNo': 'رقم الطلب',
            'InvoiceNo': 'Net Sold Qty', 
            'ItemNo': 'رقم الصنف',
            'ItemName': 'اسم الصنف',
            'NetQty': 'Net Sold Qty',
            'ReceiptNo': 'رقم الفاتورة',
            'SalesDate': 'التاريخ',
            'BranchNo': 'رقم الصيدلية',
            'Username': 'الصيدلي',
            'ProfileType': 'نوع البروفايل'
        }
        
        # التحقق من وجود الأعمدة وإعادة تسميتها بشكل متوافق تماماً مع كود المطابقة
        available_mappings = {k: v for k, v in column_mapping.items() if k in df_raw.columns}
        if available_mappings:
            df_renamed = df_raw.rename(columns=available_mappings)
            print(f"✅ تم سحب وتجهيز {len(df_renamed)} سطر فاتورة حية من قاعدة بيانات ABC بنجاح.")
            return df_renamed
        else:
            print("⚠️ تنبيه: مسميات أعمدة الـ MySQL لم تطابق الخريطة القياسية، تم تمرير الجدول الخام لمحرك الفرز.")
            return df_raw
            
    except Exception as e:
        print(f"❌ خطأ حرج: تعذر الاتصال المباشر بقاعدة بيانات ABC محلياً. السبب: {e}")
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
