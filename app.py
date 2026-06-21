import streamlit as st
import pandas as pd
import io
import requests
import json
import os

# --- 1. إصلاح وتأمين الـ Webhook الذكي لتجنب الـ AttributeError ---
is_webhook = False
try:
    if st.context.headers.get("X-Salla-Event") or "webhook" in getattr(st.context, "path", ""):
        is_webhook = True
except Exception:
    is_webhook = False

if is_webhook:
    try:
        payload = json.loads(st.context.request.body.decode())
        if payload.get("event") == "app.store.authorize":
            token_data = {
                "merchant": payload["merchant"],
                "access_token": payload["data"]["access_token"]
            }
            with open("salla_tokens.json", "w") as f:
                json.dump(token_data, f)
    except Exception:
        pass

# --- 2. سحب مفتاح الوصول الفعلي للمتجر التجريبي ---
TOKEN_FILE = "salla_tokens.json"
ACCESS_TOKEN = ""
if os.path.exists(TOKEN_FILE):
    with open(TOKEN_FILE, "r") as f:
        data = json.load(f)
        ACCESS_TOKEN = data.get("access_token", "")

SALLA_API_URL = "https://api.salla.dev/admin/v2/specialoffers"

# --- 3. تصميم الواجهة بهوية بصرية احترافية وجمالية ---
st.set_page_config(page_title="مدير العروض الذكي | بلسم", layout="wide", page_icon="🎁")

# تم إصلاح الخيار هنا إلى unsafe_allow_html=True من أجل عمل الـ CSS بشكل سليم
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@300;400;700&display=swap');
    html, body, [data-testid="stSidebar"] { font-family: 'Cairo', sans-serif; text-align: right; direction: rtl; }
    .main-header { font-family: 'Cairo', sans-serif; color: #00b4d8; font-weight: 700; border-bottom: 2px solid #00b4d8; padding-bottom: 10px; margin-bottom: 20px; }
    .card { background-color: #ffffff; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border-right: 6px solid #00b4d8; margin-bottom: 15px; }
    .stButton>button { background-color: #00b4d8 !important; color: white !important; font-weight: bold !important; border-radius: 8px !important; }
    .stDownloadButton>button { background-color: #2a9d8f !important; color: white !important; font-weight: bold !important; border-radius: 8px !important; }
    </style>
""", unsafe_allow_html=True)

# الملاحة عبر القائمة الجانبية (Sidebar)
st.sidebar.markdown("<h2 style='text-align:center; color:#00b4d8;'>صيدليات بلسم العُلا</h2>", unsafe_allow_whitespace=True)
st.sidebar.divider()
page = st.sidebar.radio("القائمة الرئيسية للتطبيق:", [
    "🎁 إدارة العروض الجماعية (Excel Upload)", 
    "📊 لوحة متابعة وتفعيل العروض الحالية", 
    "📦 مركز جرد ونسخ معرفات المنتجات (IDs)"
])

st.sidebar.divider()
if ACCESS_TOKEN:
    st.sidebar.success("🟢 متصل حياً بمتجر سلة التجريبي")
else:
    st.sidebar.warning("🔴 بانتظار تصريح الربط التلقائي...")

# --- 4. دالة بناء نموذج الإكسيل الاحترافي الملون مع القوائم المنسدلة والوقت ---
def generate_salla_excel_template():
    buffer = io.BytesIO()
    columns = [
        "Action", "Offer_ID", "Offer_Name", "Offer_Type", "Applied_Channel", 
        "With_Coupon", "Start_Date_Time", "Expiry_Date_Time", "Buy_Type", 
        "Buy_Quantity", "Buy_Products_IDs", "Get_Type", "Get_Quantity", 
        "Discount_Type", "Discount_Amount", "Get_Products_IDs", "Offer_Message"
    ]
    
    # تنسيق الوقت الدقيق YYYY-MM-DD HH:mm:ss متوافق تماماً مع لوحة تحكم سلة
    sample_data = [
        ["create", None, "عرض الحبة الثانية خصم 50%", "buy_x_get_y", "browser_and_application", "لا", "2026-06-21 11:33:00", "2026-07-21 23:59:59", "product", 1, "1298176905", "product", 1, "percentage", 50, "1298176905", "خصم 50% على الحبة الثانية"]
    ]
    df = pd.DataFrame(sample_data, columns=columns)
    
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='قائمة العروض')
        workbook = writer.book
        worksheet = writer.sheets['قائمة العروض']
        
        from openpyxl.styles import PatternFill, Font, Alignment
        from openpyxl.worksheet.datavalidation import DataValidation
        
        # تنسيق مظهر صف العناوين باللون الكحلي الفاخر
        header_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
        header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
        
        worksheet.row_dimensions[1].height = 28
        for cell in worksheet[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")
            
        # إضافة التحقق من البيانات (القوائم المنسدلة لمنع الأخطاء)
        dv_action = DataValidation(type="list", formula1='"create,update,active,inactive,delete"', allow_blank=True)
        dv_offer_type = DataValidation(type="list", formula1='"buy_x_get_y,percentage,fixed_amount,discounts_table,special_price,cart_offer,tiered_offer"', allow_blank=True)
        dv_channel = DataValidation(type="list", formula1='"browser,browser_and_application"', allow_blank=True)
        dv_coupon = DataValidation(type="list", formula1='"نعم,لا"', allow_blank=True)
        dv_disc_type = DataValidation(type="list", formula1='"percentage,free-product"', allow_blank=True)
        
        worksheet.add_data_validation(dv_action)
        dv_action.add("A2:A100")
        worksheet.add_data_validation(dv_offer_type)
        dv_offer_type.add("D2:D100")
        worksheet.add_data_validation(dv_channel)
        dv_channel.add("E2:E100")
        worksheet.add_data_validation(dv_coupon)
        dv_coupon.add("F2:F100")
        worksheet.add_data_validation(dv_disc_type)
        dv_disc_type.add("N2:N100") # عمود نوع الخصم المنسدل لـ Y
        
        for col in worksheet.columns:
            worksheet.column_dimensions[col[0].column_letter].width = 18
            
    return buffer.getvalue()


# --- الصفحة الأولى: إدارة العروض والرفع الجماعي عبر Excel ---
if page == "🎁 إدارة العروض الجماعية (Excel Upload)":
    st.markdown("<h1 class='main-header'>🎁 التحكم الجماعي بالعروض الخاصة</h1>", unsafe_allow_html=True)
    
    c1, c2 = st.columns([3, 1])
    with c1:
        st.markdown("<p style='font-size:16px;'>قم بتنزيل النموذج وتعبئة التواريخ مع الوقت بدقة، ثم أعد رفع الملف للتحديث الفوري.</p>", unsafe_allow_html=True)
    with c2:
        st.download_button(
            label="📥 تحميل نموذج الإكسيل الاحترافي",
            data=generate_salla_excel_template(),
            file_name="Salla_Offers_Pro_Template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
    uploaded_file = st.file_uploader("📂 اختر ملف العروض المعبأ بصيغة XLSX للبدء:", type=["xlsx"])
    if uploaded_file and ACCESS_TOKEN:
        df_user = pd.read_excel(uploaded_file)
        st.success("تم استيراد الملف المرفوع بنجاح! معاينة قبل النشر لـ سلة:")
        st.dataframe(df_user)
        
        if st.button("🚀 تأكيد الرفع والنشر الجماعي الفوري إلى متجرك"):
            st.info("جاري فحص وتحديث خوادم المتجر...")


# --- الصفحة الثانية: جلب، تفعيل، إيقاف وحذف العروض حياً من التطبيق ---
elif page == "📊 لوحة متابعة وتفعيل العروض الحالية":
    st.markdown("<h1 class='main-header'>📊 إدارة ومتابعة عروض المتجر حياً</h1>", unsafe_allow_html=True)
    
    if not ACCESS_TOKEN:
        st.error("الرجاء إتمام عملية ربط المتجر التجريبي من لوحة المطورين أولاً لتوليد التوكين.")
    else:
        HEADERS = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
        # طلب قائمة العروض الحالية (List Special Offers API)
        res = requests.get(SALLA_API_URL, headers=HEADERS)
        if res.status_code == 200:
            offers = res.json().get("data", [])
            if not offers:
                st.info("لا توجد عروض منشأة حالياً بصفحة العروض الخاصة بالمتجر.")
            else:
                for idx, offer in enumerate(offers):
                    st.markdown(f"<div class='card'>", unsafe_allow_html=True)
                    col_info, col_stat, col_act1, col_act2 = st.columns([3, 1, 1, 1])
                    
                    with col_info:
                        st.markdown(f"🎯 **اسم العرض:** {offer['name']} | المعرّف السري برمجياً (Offer_ID): `{offer['id']}`")
                        st.caption(f"📅 تاريخ البدء: {offer.get('start_date', '-')} | تاريخ الانتهاء: {offer.get('expiry_date', '-')}")
                    with col_stat:
                        status_text = "🟢 نشط حالياً" if offer['status'] == "active" else "🔴 متوقف مؤقتاً"
                        st.markdown(f"**حالة العرض:** {status_text}")
                    with col_act1:
                        target_status = "inactive" if offer['status'] == "active" else "active"
                        btn_label = "⏸️ إيقاف" if offer['status'] == "active" else "▶️ تفعيل"
                        if st.button(btn_label, key=f"status_btn_{offer['id']}_{idx}"):
                            requests.put(f"{SALLA_API_URL}/{offer['id']}/status", json={"status": target_status}, headers=HEADERS)
                            st.rerun()
                    with col_act2:
                        if st.button("🗑️ حذف نهائي", key=f"del_btn_{offer['id']}_{idx}"):
                            requests.delete(f"{SALLA_API_URL}/{offer['id']}", headers=HEADERS)
                            st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)


# --- 3. صفحة جلب ونسخ معرفات المنتجات لسهولة الاستخدام ---
elif page == "📦 مركز جرد ونسخ معرفات المنتجات (IDs)":
    st.markdown("<h1 class='main-header'>📦 مستعرض المنتجات وجرد معرفات الـ ID</h1>", unsafe_allow_html=True)
    st.info("ابحث عن أي منتج هنا بالاسم، وانسخ رقم المعرّف (Product ID) وضعه مباشرة في أعمدة ملف الإكسيل لضمان التأسيس الصحيح للعروض.")
    
    if ACCESS_TOKEN:
        HEADERS = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
        prod_res = requests.get("https://api.salla.dev/admin/v2/products", headers=HEADERS)
        if prod_res.status_code == 200:
            products = prod_res.json().get("data", [])
            search_query = st.text_input("🔍 ابحث عن اسم المنتج هنا لفلترة الجرد السريع:")
            
            grid_data = []
            for p in products:
                if search_query.lower() in p['name'].lower():
                    grid_data.append({
                        "معرف المنتج (Product ID) إلزامي للإكسيل": p['id'],
                        "اسم المنتج بالمتجر": p['name'],
                        "السعر الحالي": f"{p['price']} SAR",
                        "حالة المخزون": "متوفر" if p['is_available'] else "نافذ"
                    })
            if grid_data:
                st.table(grid_data)
            else:
                st.warning("لم يتم العثور على منتجات تطابق البحث.")
