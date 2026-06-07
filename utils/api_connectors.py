import requests
import json
import pandas as pd
from datetime import datetime, timedelta

# 🔑 إعدادات الربط الثابتة والمستخرجة من ملف ABCOnline.set الخاص بنظامك
ABC_BASE_URL = "https://abcsupportapi.abcsoftwares.com/api/"
ABC_API_KEY = "ABC"

def fetch_abc_invoices_via_api(days_back: int = 1) -> pd.DataFrame:
    """
    الاتصال بـ ABC Support API وجلب فواتير الفروع تلقائياً وتحويلها إلى DataFrame جاهز للمطابقة.
    """
    # تحديد النطاق الزمني للمزامنة (افتراضياً: فواتير آخر 24 ساعة)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    
    # تجهيز روابط الـ Endpoints بناءً على توثيق النظام لديك
    # ملحوظة: يتم تعديل اسم الـ Endpoint الفرعي (مثل Sales/GetInvoices) بناءً على المخطط الفعلي لجداول ABC
    endpoint = f"{ABC_BASE_URL}OnlineLicense/GetInvoices" 
    
    # إعداد ترويسة الطلب والمعاملات الآمنة (Headers & Parameters)
    headers = {
        "Authorization": f"Bearer {ABC_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    params = {
        "fromDate": start_date.strftime("%Y-%m-%d"),
        "toDate": end_date.strftime("%Y-%m-%d")
    }
    
    try:
        print(f"🔄 جاري الاتصال بنظام ABC وسحب فواتير الفترة من {params['fromDate']} إلى {params['toDate']}...")
        response = requests.get(endpoint, headers=headers, params=params, timeout=30.0)
        
        # التحقق من استجابة السيرفر بنجاح
        if response.status_code == 200:
            json_data = response.json()
            
            # استخراج مصفوفة الفواتير الفروعية (Payload)
            # نفترض هنا أن البيانات قادمة كـ List أو داخل متغير مسمى 'data' أو 'invoices'
            invoices_list = json_data.get('data', json_data) if isinstance(json_data, dict) else json_data
            
            if not invoices_list or len(invoices_list) == 0:
                print("📭 مزامنة ABC: لا توجد فواتير جديدة مسجلة بالنظام خلال هذه الفترة.")
                return pd.DataFrame()
                
            # تحويل الـ JSON المستلم إلى Pandas DataFrame فوراً في الذاكرة
            df_raw = pd.DataFrame(invoices_list)
            
            # 🧠 [هندسة التحويل والترجمة]: خريطة مطابقة الجداول وتوحيد مسميات أعمدة ABC لتطابق محرك الفرز الحالي
            # يتم تعديل مسميات الجانب الأيسر (الـ Keys) لتطابق مسميات الـ JSON القادم من سيرفر ABC لديك صراحةً
            column_mapping = {
                'OrderNo': 'رقم الطلب',
                'InvoiceNo': 'Net Sold Qty', # أو العمود المعادل للكمية الصافية في ABC
                'ItemNo': 'رقم الصنف',
                'ItemName': 'اسم الصنف',
                'NetQty': 'Net Sold Qty',
                'ReceiptNo': 'رقم الفاتورة',
                'SalesDate': 'التاريخ',
                'BranchNo': 'رقم الصيدلية',
                'Username': 'الصيدلي',
                'ProfileType': 'نوع البروفايل'
            }
            
            # التحقق من وجود الأعمدة وإعادة تسميتها بشكل متوافق تماماً
            available_mappings = {k: v for k, v in column_mapping.items() if k in df_raw.columns}
            if available_mappings:
                df_renamed = df_raw.rename(columns=available_mappings)
                print(f"✅ تم سحب وتجهيز {len(df_renamed)} سطر فاتورة من ABC بنجاح عبر الـ API.")
                return df_renamed
            else:
                # في حال كانت الأسماء قادمة بالعربية أو بهيكل مختلف، نتركها كما هي ليقوم الـ find_column في الفرز باصطيادها
                print("⚠️ تنبيه: مسميات الـ API لم تطابق الخريطة القياسية، سيتم تمرير الجدول الخام إلى محرك الفرز.")
                return df_raw
        else:
            print(f"❌ فشل الاتصال بسيرفر ABC. كود الخطأ من السيرفر: {response.status_code}")
            return pd.DataFrame()
            
    except requests.exceptions.Timeout:
        print("❌ خطأ: انتهت مهلة الاتصال بسيرفر ABC (Timeout) - السيرفر مستغرق في الاستجابة.")
        return pd.DataFrame()
    except Exception as e:
        print(f"❌ خطأ غير متوقع أثناء سحب بيانات فواتير ABC عبر الـ API: {e}")
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
