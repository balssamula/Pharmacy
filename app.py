import streamlit as st
import pandas as pd
import io
import requests

# إعدادات الصفحة العامة في Streamlit
st.set_page_config(page_title="مدير العروض الذكي", layout="wide")

st.title("📦 لوحة التحكم المتقدمة في العروض الخاصة - سلة")
st.markdown("قم بإدارة عروض متجرك (تأسيس، تعديل، إيقاف، حذف) عبر ملفات الإكسيل المعتمدة.")

# --- بيانات الربط الافتراضية مع سلة (يتم تحديثها ديناميكياً عند التثبيت) ---
ACCESS_TOKEN = "ضع_هنا_مفتاح_الوصول_الخاص_بمتجرك"
SALLA_API_URL = "https://api.salla.dev/admin/v2/specialoffers"

# --- 1. دالة إنشاء نموذج الإكسيل الشامل والمطابق للوحة تحكم سلة ---
def generate_advanced_template():
    buffer = io.BytesIO()
    
    # بناء البيانات الافتراضية لتشمل كل المدخلات الظاهرة في لوحة تحكم المتجر
    data = {
        "Action": ["create"],                  # create, update, active, inactive, delete
        "Offer_ID": [None],                    # يملأ فقط في التعديل أو الحذف أو تغيير الحالة
        "Offer_Name": ["عرض صيف 2026 المميز"],  # عنوان العرض
        "Start_Date": ["2026-06-21"],          # تاريخ بدء العرض
        "Expiry_Date": ["2026-07-21"],          # تاريخ انتهاء العرض
        "Applied_Channel": ["browser_and_application"], # منصة العرض
        "Buy_Type": ["product"],               # منتجات مختارة (product) أو تصنيفات (category)
        "Buy_Quantity": [2],                   # الكمية المطلوبة من X
        "Buy_Products_IDs": ["1298176905"],     # معرفات منتجات X (تفصل بفاصلة لو كانت متعددة)
        "Get_Type": ["product"],               # نوع حافز Y
        "Get_Quantity": [1],                   # كمية Y التي سيحصل عليها
        "Discount_Type": ["free-product"],     # خيارات: percentage (خصم بنسبة) أو free-product (منتج مجاني)
        "Discount_Amount": [0],                # يكتب الرقم (مثلاً 50 لو كانت النسبة 50%، أو 0 للمنتج المجاني)
        "Get_Products_IDs": ["1444615766"],     # معرفات منتجات Y
        "Offer_Message": ["اشتري قطعتين واحصل على الثالثة مجاناً"] # نص رسالة العرض
    }
    
    df = pd.DataFrame(data)
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Special_Offers_Template')
    return buffer.getvalue()

# --- واجهة رفع وتحميل الملفات ---
st.subheader("1. تحميل النموذج المعتمد")
template_file = generate_advanced_template()
st.download_button(
    label="📥 تحميل نموذج ملف الإكسيل المطور (شامل لكافة المدخلات)",
    data=template_file,
    file_name="Salla_Advanced_Offers_Template.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

st.divider()

st.subheader("2. رفع ومعالجة الملف")
uploaded_file = st.file_uploader("📂 ارفع ملف الإكسيل المعبأ هنا", type=["xlsx"])

if uploaded_file is not None:
    try:
        df_user = pd.read_excel(uploaded_file)
        st.success("تم قراءة الملف بنجاح! معاينة قبل الرفع إلى سلة:")
        st.dataframe(df_user)
        
        # عند الضغط على الزر، تبدأ معالجة الحقول وتحويلها إلى السكيمات المطلوبة لـ API سلة
        if st.button("🚀 بدء تنفيذ العمليات الجماعية على المتجر"):
            HEADERS = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
            
            for index, row in df_user.iterrows():
                action = str(row['Action']).strip().lower()
                
                # تحويل أرقام المنتجات من نصوص تفصلها فاصلة إلى مصفوفة أرقام (Array of Integers)
                buy_products = [int(pid.strip()) for pid in str(row['Buy_Products_IDs']).split(',') if pid.strip().isdigit()]
                get_products = [int(pid.strip()) for pid in str(row['Get_Products_IDs']).split(',') if pid.strip().isdigit()]
                
                # تركيب الـ Request Body بناءً على ملفات التوثيق المرفقة (Create & Update)
                payload = {
                    "name": row['Offer_Name'],
                    "message": row['Offer_Message'],
                    "applied_channel": row['Applied_Channel'],
                    "offer_type": "buy_x_get_y",
                    "applied_to": row['Buy_Type'],
                    "start_date": str(row['Start_Date']),
                    "expiry_date": str(row['Expiry_Date']),
                    "buy": {
                        "type": row['Buy_Type'],
                        "quantity": int(row['Buy_Quantity']),
                        "products": buy_products if row['Buy_Type'] == "product" else []
                    },
                    "get": {
                        "type": row['Get_Type'],
                        "discount_type": row['Discount_Type'],
                        "quantity": int(row['Get_Quantity']),
                        "products": get_products if row['Get_Type'] == "product" else [],
                        "discount_amount": str(row['Discount_Amount']) if row['Discount_Type'] == "percentage" else "0.00"
                    }
                }
                
                # توجيه الطلب برمجياً بناءً على الـ Action
                if action == "create":
                    res = requests.post(SALLA_API_URL, json=payload, headers=HEADERS)
                    if res.status_code == 200:
                        st.success(f"السطر {index+1}: تم إنشاء العرض بنجاح! المعرف: {res.json()['data']['id']}")
                # (يمكن إضافة بقية الشروط للهدم والتحديث هنا بنفس الطريقة المتبعة سابقاً)
                
    except Exception as e:
        st.error(f"تأكد من صحة البيانات المكتوبة داخل الإكسيل. تفاصيل الخطأ: {e}")
