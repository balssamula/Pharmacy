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
    
    # 1. بناء البيانات الأساسية للنموذج
    columns = [
        "Action", "Offer_ID", "Offer_Name", "Offer_Type", "Applied_Channel", 
        "With_Coupon", "Start_Date", "Expiry_Date", "Buy_Type", "Buy_Quantity", 
        "Buy_Products_IDs", "Get_Type", "Get_Quantity", "Discount_Type", 
        "Discount_Amount", "Get_Products_IDs", "Offer_Message"
    ]
    
    # أسطر استرشادية كمثال للمستخدم
    sample_data = [
        ["create", None, "عرض قطعتين والثالثة مجاناً", "buy_x_get_y", "browser_and_application", "نعم", "2026-06-21", "2026-07-21", "product", 2, "1298176905", "product", 1, "free-product", 0, "1444615766", "اشتري قطعتين واحصل على الثالثة مجاناً"],
        ["update", 374680268, "تعديل العرض الحالي", "percentage", "browser_and_application", "لا", "2026-06-21", "2026-08-15", "product", 1, "1298176905", "product", 1, "percentage", 50, "1444615766", "خصم 50% على المنتج الثاني"]
    ]
    
    df = pd.DataFrame(sample_data, columns=columns)
    
    # 2. الكتابة والتنسيق باستخدام openpyxl
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='إدارة العروض الجماعية')
        
        workbook = writer.book
        worksheet = writer.sheets['إدارة العروض الجماعية']
        
        # استيراد أدوات التنسيق والتحقق من البيانات
        from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
        from openpyxl.worksheet.datavalidation import DataValidation
        
        # تنسيق صف العناوين (الأزرق الداكن والخط الأبيض العريض)
        header_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
        header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
        center_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        
        thin_side = Side(border_style="thin", color="D9D9D9")
        thin_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)
        
        # تطبيق التنسيق على الصف الأول
        worksheet.row_dimensions[1].height = 28
        for cell in worksheet[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = center_alignment
            cell.border = thin_border
            
        # تنسيق صفوف البيانات وتوسيع الأعمدة تلقائياً
        for row in worksheet.iter_rows(min_row=2, max_row=100):
            for cell in row:
                cell.font = Font(name="Segoe UI", size=10)
                cell.alignment = Alignment(horizontal="center", vertical="center")
                cell.border = thin_border
                
        for col in worksheet.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = col[0].column_letter
            worksheet.column_dimensions[col_letter].width = max(max_len + 3, 15)
            
        # 3. إضافة القوائم المنسدلة (Dropdown) لمنع أخطاء الإدخال
        dv_action = DataValidation(type="list", formula1='"create,update,active,inactive,delete"', allow_blank=True)
        dv_type = DataValidation(type="list", formula1='"buy_x_get_y,percentage,fixed_amount,discounts_table,special_price,cart_offer,tiered_offer"', allow_blank=True)
        dv_channel = DataValidation(type="list", formula1='"browser,browser_and_application"', allow_blank=True)
        dv_coupon = DataValidation(type="list", formula1='"نعم,لا"', allow_blank=True)
        
        # ربط القوائم المنسدلة بالأعمدة المخصصة لها حتى الصف 100
        worksheet.add_data_validation(dv_action)
        dv_action.add("A2:A100") # عمود الإجراء
        
        worksheet.add_data_validation(dv_type)
        dv_type.add("D2:D100")   # عمود نوع العرض
        
        worksheet.add_data_validation(dv_channel)
        dv_channel.add("E2:E100") # عمود القناة المطبقة
        
        worksheet.add_data_validation(dv_coupon)
        dv_coupon.add("F2:F100")   # عمود التطبيق مع كوبون
        
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
