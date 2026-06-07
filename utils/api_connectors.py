import requests
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
