import streamlit as st
import pandas as pd
import io
import requests

# إعدادات واجهة المستخدم في Streamlit
st.set_page_config(page_title="مدير العروض الذكي", layout="wide")

st.title("📦 لوحة تحكم إدارة العروض الخاصة الجماعية - سلة")
st.markdown("تحكم في تأسيس، تعديل، إيقاف، وحذف العروض الخاصة بمتجرك عبر ملف إكسيل موحد.")

# --- 1. مفاتيح الوصول والربط مع سلة ---
# ملحوظة: يمكنك قراءة هذا المفتاح ديناميكياً من ملف salla_tokens.json الذي يستقبله ملف Webhook.py
ACCESS_TOKEN = "ضع_هنا_مفتاح_الوصول_الخاص_بمتجرك"
SALLA_API_URL = "https://api.salla.dev/admin/v2/specialoffers"

# --- 2. توليد نموذج الإكسيل الشامل والمطابق للوحة تحكم سلة ---
def generate_salla_template():
    buffer = io.BytesIO()
    
    # بناء الهيكل المتوافق مع شاشات سلة والـ APIs المرفقة
    data = {
        "Action": ["create", "update", "inactive", "delete"], # نوع الإجراء المطلوب
        "Offer_ID": [None, 374680268, 843056940, 204285485], # المعرف (مطلوب لكل العمليات عدا الإنشاء)
        "Offer_Name": ["عرض صيف 2026 المميز", "تعديل عرض قائم", "إيقاف العرض مؤقتاً", "حذف العرض نهائياً"],
        "Start_Date": ["2026-06-21", "2026-06-21", None, None],
        "Expiry_Date": ["2026-07-21", "2026-08-15", None, None],
        "Applied_Channel": ["browser_and_application", "browser_and_application", None, None],
        "Buy_Type": ["product", "product", None, None],         # نوع الشراء X (product أو category)
        "Buy_Quantity": [2, 1, None, None],                     # كمية X المطلوبة
        "Buy_Products_IDs": ["1298176905", "1298176905", None, None], # معرفات منتجات X تفصل بفاصلة
        "Get_Type": ["product", "product", None, None],         # نوع منح Y
        "Get_Quantity": [1, 1, None, None],                     # كمية Y الممنوحة
        "Discount_Type": ["free-product", "percentage", None, None], # free-product لمنتج مجاني، percentage لخصم بنسبة
        "Discount_Amount": [0, 50, None, None],                 # 0 للمنتج المجاني، أو الرقم مباشرة للنسبة (مثال: 50 لـ 50%)
        "Get_Products_IDs": ["1444615766", "1444615766", None, None], # معرفات منتجات Y
        "Offer_Message": ["اشتري قطعتين واحصل على الثالثة مجاناً", "خصم 50% على المنتج الثاني", None, None]
    }
    
    df = pd.DataFrame(data)
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Salla_Offers')
    return buffer.getvalue()

# --- 3. واجهة المستخدم لرفع وتحميل الملفات ---
st.subheader("1. تحميل النموذج المعتمد")
template_file = generate_salla_template()
st.download_button(
    label="📥 تحميل نموذج ملف الإكسيل المطور (شامل لكافة العمليات)",
    data=template_file,
    file_name="Salla_Offers_Advanced_Template.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

st.divider()

st.subheader("2. رفع الملف وتحديث المتجر دفعة واحدة")
uploaded_file = st.file_uploader("📂 اسحب وأفلت ملف الإكسيل المعبأ هنا", type=["xlsx"])

if uploaded_file is not None:
    try:
        df_user = pd.read_excel(uploaded_file)
        st.success("تمت قراءة الملف بنجاح! معاينة البيانات قبل الإرسال للمتجر:")
        st.dataframe(df_user)
        
        # عند الضغط على الزر تبدأ المعالجة الذكية لكل سطر وتوجيهه للـ API المناسب في سلة
        if st.button("🚀 بدء تنفيذ العمليات الجماعية على متجر سلة"):
            HEADERS = {
                "Authorization": f"Bearer {ACCESS_TOKEN}",
                "Content-Type": "application/json"
            }
            
            for index, row in df_user.iterrows():
                action = str(row['Action']).strip().lower()
                offer_id = row.get('Offer_ID')
                
                # تحويل أرقام المنتجات من نص يفصله فاصلة إلى قائمة أرقام برمجية (Array of Integers) كما تتوقعها واجهات سلة
                buy_products = [int(pid.strip()) for pid in str(row.get('Buy_Products_IDs', '')).split(',') if pid.strip().isdigit()]
                get_products = [int(pid.strip()) for pid in str(row.get('Get_Products_IDs', '')).split(',') if pid.strip().isdigit()]
                
                # تجهيز السكيمة (Payload) الخاصة بالإنشاء والتعديل
                payload = {
                    "name": row.get('Offer_Name'),
                    "message": row.get('Offer_Message'),
                    "applied_channel": row.get('Applied_Channel', 'browser_and_application'),
                    "offer_type": "buy_x_get_y",
                    "applied_to": row.get('Buy_Type', 'product'),
                    "start_date": str(row.get('Start_Date')),
                    "expiry_date": str(row.get('Expiry_Date')),
                    "buy": {
                        "type": row.get('Buy_Type', 'product'),
                        "quantity": int(row.get('Buy_Quantity', 1)) if pd.notna(row.get('Buy_Quantity')) else 1,
                        "products": buy_products
                    },
                    "get": {
                        "type": row.get('Get_Type', 'product'),
                        "discount_type": row.get('Discount_Type', 'free-product'),
                        "quantity": int(row.get('Get_Quantity', 1)) if pd.notna(row.get('Get_Quantity')) else 1,
                        "products": get_products,
                        "discount_amount": str(row.get('Discount_Amount', 0)) if row.get('Discount_Type') == "percentage" else "0.00"
                    }
                }
                
                # --- الفحص والتوجيه الذكي بناءً على حقل Action وعمود الـ API المتوافق ---
                
                # 1. حالة الإنشاء الجماعي (Create Special Offer)
                if action == "create":
                    res = requests.post(SALLA_API_URL, json=payload, headers=HEADERS)
                    if res.status_code == 200:
                        st.success(f"السطر {index+1}: تم إنشاء العرض بنجاح! المعرف الجديد هو: {res.json()['data']['id']}")
                    else:
                        st.error(f"السطر {index+1}: فشل الإنشاء. السبب: {res.text}")
                        
                # 2. حالة التحديث والتعديل (Update Special Offer)
                elif action == "update" and pd.notna(offer_id):
                    update_url = f"{SALLA_API_URL}/{int(offer_id)}"
                    res = requests.put(update_url, json=payload, headers=HEADERS)
                    if res.status_code == 200:
                        st.success(f"السطر {index+1}: تم تحديث العرض رقم {int(offer_id)} بنجاح.")
                    else:
                        st.error(f"السطر {index+1}: فشل تحديث العرض رقم {int(offer_id)}. السبب: {res.text}")
                        
                # 3. حالة تفعيل أو إيقاف العرض (Change Special Offer Status)
                elif action in ["active", "inactive"] and pd.notna(offer_id):
                    status_url = f"{SALLA_API_URL}/{int(offer_id)}/status"
                    status_payload = {"status": action}
                    res = requests.put(status_url, json=status_payload, headers=HEADERS)
                    if res.status_code == 200:
                        st.success(f"السطر {index+1}: تم تغيير حالة العرض رقم {int(offer_id)} إلى ({action}) بنجاح.")
                    else:
                        st.error(f"السطر {index+1}: فشل تغيير حالة العرض رقم {int(offer_id)}. السبب: {res.text}")
                        
                # 4. حالة الحذف النهائي للعرض (Delete Special Offer)
                elif action == "delete" and pd.notna(offer_id):
                    delete_url = f"{SALLA_API_URL}/{int(offer_id)}"
                    res = requests.delete(delete_url, headers=HEADERS)
                    if res.status_code == 200:
                        st.success(f"السطر {index+1}: تم حذف العرض رقم {int(offer_id)} نهائياً من المتجر.")
                    else:
                        st.error(f"السطر {index+1}: فشل حذف العرض رقم {int(offer_id)}. السبب: {res.text}")
                        
            st.info("✨ تم الانتهاء من معالجة كافة الأسطر وتحديث متجرك في سلة.")
            
    except Exception as e:
        st.error(f"تأكد من مطابقة الملف المرفوع للنموذج المعتمد ومن صحة البيانات. تفاصيل الخطأ: {e}")
