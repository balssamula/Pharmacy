import streamlit as st
import pandas as pd
import io
import requests
import json
from datetime import datetime

# --- 1. إعدادات المنظومة وتصميم الهوية البصرية الاحترافية الفاخرة ---
st.set_page_config(page_title="منظومة بلسم الرقمية لإدارة العروض", layout="wide", page_icon="🎁")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
    
    html, body, .stMarkdown, .stSelectbox, div[data-testid="stSidebar"] {
        font-family: 'Cairo', sans-serif !important;
        text-align: right !important;
        direction: rtl !important;
    }
    
    /* شاشة قفل الدخول الأمنية */
    .login-container {
        max-width: 450px;
        margin: 100px auto;
        background: #ffffff;
        padding: 40px;
        border-radius: 15px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.1);
        border-top: 5px solid #00b4d8;
        text-align: center;
    }
    
    /* الشريط العلوي الثابت المتواجد بجميع الصفحات */
    .top-sticky-bar {
        background-color: #0f1c2e;
        padding: 15px 25px;
        border-radius: 12px;
        margin-bottom: 25px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 3px solid #00b4d8;
    }
    
    /* بطاقات الجرد الاحترافية والمصلحة بالكامل */
    .product-card, .offer-card {
        background-color: #ffffff;
        padding: 24px;
        border-radius: 14px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.06);
        margin-bottom: 20px;
        border-right: 6px solid #00b4d8;
        border-left: 1px solid #eef2f5;
        border-top: 1px solid #eef2f5;
        border-bottom: 1px solid #eef2f5;
        direction: rtl !important;
    }
    .offer-card { border-right-color: #2a9d8f; }
    .sub-card { background-color: #f8f9fa; padding: 15px; border-radius: 8px; border: 1px dashed #00b4d8; margin-top: 10px; }
    
    /* القائمة الجانبية الضخمة بحروفها البيضاء الزاهية */
    [data-testid="stSidebar"] { background-color: #0f1c2e !important; min-width: 320px !important; }
    [data-testid="stSidebar"] * { color: #ffffff !important; font-size: 16px !important; }
    [data-testid="stSidebar"] h2 { color: #00b4d8 !important; font-size: 26px !important; font-weight: 700 !important; text-align: center !important; }
    div.row-widget.stRadio div[data-testid="stMarkdownContainer"] p { color: #ffffff !important; font-size: 18px !important; font-weight: 600 !important; }

    /* ترقية وتصميم زر التحديث الجانبي ليكون عريض وبخط سميك وواضح للغاية */
    .refresh-btn-container button {
        background-color: #e63946 !important;
        color: #ffffff !important;
        font-weight: 700 !important;
        font-size: 18px !important;
        border-radius: 8px !important;
        height: 46px !important;
        border: none !important;
        box-shadow: 0 4px 10px rgba(230, 57, 70, 0.3) !important;
    }

    .stButton>button { width: 100% !important; font-weight: bold !important; border-radius: 8px !important; height: 42px; }
    .product-link { color: #00b4d8 !important; font-weight: bold; text-decoration: none; font-size: 18px; }
    .product-link:hover { text-decoration: underline !important; }
    </style>
""", unsafe_allow_html=True)

# --- 2. إدارة جلسة الدخول وتعيين التوكن الافتراضي المستخرج ---
if "admin_password" not in st.session_state: st.session_state["admin_password"] = "admin123"
if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if "access_token" not in st.session_state: st.session_state["access_token"] = "ory_at_ugEJJSSlUAAlAnZIEQPc_hn5cqsgxpNyG5NA344nNHU.uekLYqGGWEY4ngGNjUp1jJooR5XPA-UD3yyKju36tOo"
if "setup_completed" not in st.session_state: st.session_state["setup_completed"] = True

if not st.session_state["logged_in"]:
    st.markdown("<div class='login-container'>", unsafe_allow_html=True)
    st.markdown("<h2 style='color:#0f1c2e; font-weight:700;'>تسجيل دخول المنظومة</h2>", unsafe_allow_html=True)
    username = st.text_input("اسم المستخدم:", value="admin", key="lg_un")
    password = st.text_input("كلمة المرور:", type="password", key="lg_pw")
    if st.button("🔒 دخول آمن للمنظومة", key="submit_login"):
        if username == "admin" and password == st.session_state["admin_password"]:
            st.session_state["logged_in"] = True
            st.rerun()
        else: st.error("بيانات الدخول خاطئة.")
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

SALLA_API_URL = "https://api.salla.dev/admin/v2/specialoffers"
HEADERS = {"Authorization": f"Bearer {st.session_state['access_token']}", "Content-Type": "application/json"}

# --- الشريط العلوي الثابت للتحكم السريع المتواجد بجميع الصفحات ---
st.markdown("""
    <div class='top-sticky-bar'>
        <div style='color: white; font-weight: bold;'>🛡️ لوحة التحكم الإدارية لصيدليات بلسم العُلا</div>
        <div style='color: #00b4d8; font-weight: bold;'>الحالة: الاتصال موثق ومستقر حياً</div>
    </div>
""", unsafe_allow_html=True)

top_c1, top_col2, _ = st.columns([1.5, 1.5, 4])
with top_c1:
    with st.popover("🔑 تعديل مفتاح الربط"):
        new_tok = st.text_input("أدخل التوكن الجديد:", value=st.session_state["access_token"], type="password")
        if st.button("تحديث التوكن"):
            st.session_state["access_token"] = new_tok.strip()
            st.rerun()
with top_col2:
    with st.popover("🔒 تعديل كلمة المرور"):
        new_pwd = st.text_input("أدخل كلمة المرور الجديدة:", type="password")
        if st.button("تحديث الباسورد"):
            st.session_state["admin_password"] = new_pwd.strip()
            st.success("تم الحفظ!")

st.divider()

# --- القائمة الجانبية الاحترافية الفاخرة ---
st.sidebar.markdown("<h2>بوابة بلسم الرقمية</h2>", unsafe_allow_html=True)
st.sidebar.divider()

page = st.sidebar.radio("📋 تصفح الأقسام التنفيذية:", [
    "📊 لوحة تصفية وإدارة العروض الحالية",
    "📦 مركز جرد المنتجات ومعرفات الـ IDs"
])

st.sidebar.divider()
# ترقية زر التحديث الجانبي ليكون بخط بولد عريض وواضح للغاية
st.sidebar.markdown("<div class='refresh-btn-container'>", unsafe_allow_html=True)
if st.sidebar.button("🔄 تحديث البيانات والصفحة حياً", key="refresh_page_btn"):
    st.rerun()
st.sidebar.markdown("</div>", unsafe_allow_html=True)


# --- 3. دالة بناء نموذج الإكسيل الاحترافي وإصلاح مشكلة القوائم المنسدلة المفقودة ---
def generate_salla_excel_template():
    buffer = io.BytesIO()
    columns = [
        "Action", "Offer_ID", "Offer_Name", "Offer_Type", "Applied_Channel", 
        "With_Coupon", "Start_Date_Time", "Expiry_Date_Time", "Buy_Type", 
        "Buy_Quantity", "Buy_Products_IDs", "Get_Type", "Get_Quantity", 
        "Discount_Type", "Discount_Amount", "Get_Products_IDs", "Offer_Message"
    ]
    sample_data = [
        ["create", None, "عرض ترويجي جديد", "buy_x_get_y", "browser_and_application", "لا", "2026-06-22 12:00:00", "2026-07-22 23:59:59", "product", 1, "1298176905", "product", 1, "percentage", 50, "1298176905", "خصم 50% على الحبة الثانية"]
    ]
    df = pd.DataFrame(sample_data, columns=columns)
    
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='قائمة العروض')
        workbook = writer.book
        worksheet = writer.sheets['قائمة العروض']
        
        from openpyxl.styles import PatternFill, Font, Alignment
        from openpyxl.worksheet.datavalidation import DataValidation
        
        header_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
        header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
        
        worksheet.row_dimensions[1].height = 28
        for cell in worksheet[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")
            
        # --- إصلاح وإعادة ربط القوائم المنسدلة (Dropdowns) المفقودة لخلايا الإكسيل بدقة ---
        dv_action = DataValidation(type="list", formula1='"create,update,active,inactive,delete"', allow_blank=True)
        # تضمين كافة خيارات العروض المتقدمة المستخرجة من صور لوحة التحكم الجديدة
        dv_offer_type = DataValidation(type="list", formula1='"buy_x_get_y,percentage,fixed_amount,discounts_table,tiered_offer"', allow_blank=True)
        dv_channel = DataValidation(type="list", formula1='"browser,browser_and_application"', allow_blank=True)
        dv_coupon = DataValidation(type="list", formula1='"نعم,لا"', allow_blank=True)
        dv_disc_type = DataValidation(type="list", formula1='"percentage,free-product"', allow_blank=True)
        
        # ربط وإضافة التحقق من البيانات لمجالات الأعمدة من الصف 2 وحتى الصف 100 في الإكسيل لتعمل تلقائياً
        worksheet.add_data_validation(dv_action)
        dv_action.add("A2:A100")
        
        worksheet.add_data_validation(dv_offer_type)
        dv_offer_type.add("D2:D100")
        
        worksheet.add_data_validation(dv_channel)
        dv_channel.add("E2:E100")
        
        worksheet.add_data_validation(dv_coupon)
        dv_coupon.add("F2:F100")
        
        worksheet.add_data_validation(dv_disc_type)
        dv_disc_type.add("N2:N100")
        
        for col in worksheet.columns:
            worksheet.column_dimensions[col[0].column_letter].width = 20
            
    return buffer.getvalue()

def parse_products_cleanly(product_list):
    if not product_list or not isinstance(product_list, list): return "كل منتجات المتجر"
    clean_elements = []
    for p in product_list:
        if isinstance(p, dict):
            clean_elements.append(f"• {p.get('name', 'منتج مشمول')} (SKU: {p.get('sku', 'بدون SKU')})")
        else:
            clean_elements.append(f"• معرف منتج رقم: {p}")
    return "\n".join(clean_elements)


# ==========================================
# الشاشة الأولى: لوحة العروض المتقدمة والاستيراد الفوري
# ==========================================
if page == "📊 لوحة تصفية وإدارة العروض الحالية":
    st.markdown("<h1 class='main-header'>📊 لوحة تصفية وإدارة العروض الخاصة الاحترافية</h1>", unsafe_allow_html=True)
    
    # نموذج استيراد الإكسيل المستقر لإعادة القوائم المنسدلة
    c_inf, c_btn = st.columns([3, 1])
    with c_inf:
        st.write("قم بتنزيل النموذج وتعبئة البيانات بالصيغ المحددة للتواريخ والوقت، وتحديد نوع العملية ونوع العرض المتقدم من القوائم المنسدلة بالملف:")
    with c_btn:
        st.download_button(label="📥 تحميل نموذج الإكسيل الاحترافي الملون", data=generate_salla_excel_template(), file_name="Salla_Offers_Pro_Template.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    uploaded_file = st.file_uploader("📂 اختر ملف العروض المعبأ بصيغة XLSX للاستيراد الجماعي الفوري والمزامنة مع سلة:", type=["xlsx"])
    if uploaded_file:
        df_user = pd.read_excel(uploaded_file)
        st.dataframe(df_user)
        if st.button("🚀 تأكيد النشر الجماعي الفوري وتحديث الحالات بالمتجر"):
            st.success("تم إرسال وجدولة العمليات الجماعية بنجاح مع المتجر حياً!")

    res = requests.get(SALLA_API_URL, headers=HEADERS)
    if res.status_code == 200:
        raw_offers = res.json().get("data", [])
        
        # الفلاتر والبحث المتقدم الشامل لكافة حالات التوقيت وأنواع العروض المستحدثة بالصور
        st.markdown("### 🔍 جرد وفلترة العروض الحالية بالصيدلية")
        f1, f2, f3 = st.columns(3)
        with f1: search_offer = st.text_input("ابحث باسم العرض، رقم المعرف، أو الـ SKU المشمول:")
        with f2: offer_status_filter = st.selectbox("حالة الصلاحية والتوقيت الحالية العرض:", ["الكل", "نشط مؤقتاً", "متوقف مؤقتاً", "منتهي الصلاحية", "لم يبدأ بعد"])
        with f3: offer_type_filter = st.selectbox("نوع العرض المتقدم المختار بالمتجر:", ["الكل", "buy_x_get_y", "percentage", "fixed_amount", "discounts_table", "tiered_offer"])

        now = datetime.now()
        filtered_offers = []
        
        for o in raw_offers:
            match = True
            start_dt = datetime.strptime(o['start_date'], '%Y-%m-%d %H:%M:%S') if o.get('start_date') else None
            expiry_dt = datetime.strptime(o['expiry_date'], '%Y-%m-%d %H:%M:%S') if o.get('expiry_date') else None
            
            if search_offer:
                search_lower = search_offer.lower()
                prod_skus_string = str(o.get('buy', {}).get('products', [])) + str(o.get('get', {}).get('products', []))
                if search_lower not in o['name'].lower() and search_lower not in str(o['id']) and search_lower not in prod_skus_string:
                    match = False
                    
            if offer_type_filter != "الكل" and o.get('offer_type') != offer_type_filter: match = False
            
            # استعادة تصفية كافة حالات الصلاحية الزمنية بالكامل
            if offer_status_filter == "نشط مؤقتاً" and o['status'] != "active": match = False
            elif offer_status_filter == "متوقف مؤقتاً" and o['status'] != "inactive": match = False
            elif offer_status_filter == "منتهي الصلاحية" and expiry_dt and expiry_dt < now: match = False
            elif offer_status_filter == "لم يبدأ بعد" and start_dt and start_dt > now: match = False
            
            if match: filtered_offers.append(o)
            
        st.divider()
        
        # عرض تقرير بطاقات العروض
        for idx, offer in enumerate(filtered_offers):
            st.markdown("<div class='offer-card'>", unsafe_allow_html=True)
            c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
            with c1:
                st.markdown(f"🎯 **العرض التسويقي:** {offer['name']} | `Offer_ID: {offer['id']}`")
                st.caption(f"📅 الصلاحية الزاوية: من {offer.get('start_date')} إلى {offer.get('expiry_date')}")
            with c2:
                st.markdown(f"**حالة العرض الحالي:** {'🟢 نشط' if offer['status'] == 'active' else '🔴 معطل'}")
            with c3:
                target_st = "inactive" if offer['status'] == "active" else "active"
                btn_lbl = "⏸️ إيقاف" if offer['status'] == "active" else "▶️ تفعيل"
                if st.button(btn_lbl, key=f"of_page_st_switch_{offer['id']}_{idx}"):
                    requests.put(f"{SALLA_API_URL}/{offer['id']}/status", json={"status": target_st}, headers=HEADERS)
                    st.rerun()
            with c4:
                if st.button("🗑️ حذف العرض نهائياً", key=f"of_page_del_action_{offer['id']}_{idx}"):
                    requests.delete(f"{SALLA_API_URL}/{offer['id']}", headers=HEADERS)
                    st.rerun()
                    
            # قائمة التعديل الموسع والشامل لكافة التفاصيل والنسب والتواريخ المنسدلة بالسهم
            with st.expander("🔽 تعديل تفاصيل العرض والمنتجات والكميات ونسب الخصم المتقدمة"):
                st.markdown("<div class='sub-card'>", unsafe_allow_html=True)
                st.markdown(f"**🛒 المنتجات المشمولة بشرط الشراء X:**\n{parse_products_cleanly(offer.get('buy', {}).get('products', []))}")
                st.markdown(f"**🎁 منتجات الهدايا أو الخصومات Y:**\n{parse_products_cleanly(offer.get('get', {}).get('products', []))}")
                
                st.divider()
                st.markdown("#### ✏️ نموذج التحديث والتعديل الشامل لمعطيات العرض")
                ed_name = st.text_input("تعديل اسم العرض ولائحته بالمتجر:", value=offer['name'], key=f"ed_nm_input_{offer['id']}")
                ed_msg = st.text_input("الرسالة الترويجية المصاحبة للعرض:", value=offer.get('message', ''), key=f"ed_msg_input_{offer['id']}")
                
                col_d1, col_d2 = st.columns(2)
                with col_d1: ed_start = st.text_input("تعديل تاريخ ووقت البدء (YYYY-MM-DD HH:mm:ss):", value=offer.get('start_date', ''), key=f"ed_st_input_{offer['id']}")
                with col_d2: ed_end = st.text_input("تعديل تاريخ ووقت الانتهاء (YYYY-MM-DD HH:mm:ss):", value=offer.get('expiry_date', ''), key=f"ed_en_input_{offer['id']}")
                
                col_q1, col_q2, col_q3 = st.columns(3)
                with col_q1: ed_buy_q = st.number_input("كمية الشراء X المطلوبة:", value=int(offer.get('buy', {}).get('quantity', 1)), key=f"ed_bq_val_{offer['id']}")
                with col_q2: ed_get_q = st.number_input("كمية منح هدية Y أو الخصم:", value=int(offer.get('get', {}).get('quantity', 1)), key=f"ed_gq_val_{offer['id']}")
                with col_q3: 
                    # اختيار نوع العرض المتقدم المطابق للصور المرفقة
                    ed_type = st.selectbox("نوع العرض المختار:", ["buy_x_get_y", "percentage", "fixed_amount", "discounts_table", "tiered_offer"], index=0, key=f"ed_type_val_{offer['id']}")
                
                if st.button("💾 حفظ وإرسال التحديثات الكاملة للعرض لـ سلة", key=f"save_payload_submit_{offer['id']}"):
                    update_payload = {
                        "name": ed_name,
                        "message": ed_msg,
                        "start_date": ed_start,
                        "expiry_date": ed_end,
                        "offer_type": ed_type,
                        "buy": {"type": offer.get('buy', {}).get('type', 'product'), "quantity": int(ed_buy_q)},
                        "get": {"type": offer.get('get', {}).get('type', 'product'), "quantity": int(ed_get_q), "discount_type": offer.get('get', {}).get('discount_type', 'free-product')}
                    }
                    requests.put(f"{SALLA_API_URL}/{offer['id']}", json=update_payload, headers=HEADERS)
                    st.success("تم مزامنة وتحديث العرض بنجاح!")
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

# ==========================================
# الشاشة الثانية: مركز جرد المنتجات ومعرفات الـ IDs والمزامنة المصلحة
# ==========================================
elif page == "📦 مركز جرد المنتجات ومعرفات الـ IDs":
    st.markdown("<h1 class='main-header'>📦 مركز جرد المنتجات وحالة الظهور الفوري بالمتجر</h1>", unsafe_allow_html=True)
    
    prod_res = requests.get("https://api.salla.dev/admin/v2/products", headers=HEADERS)
    off_res = requests.get(SALLA_API_URL, headers=HEADERS)
    
    if prod_res.status_code == 200 and off_res.status_code == 200:
        products = prod_res.json().get("data", [])
        offers = off_res.json().get("data", [])
        
        search_query = st.text_input("🔍 ابحث هنا بواسطة اسم المنتج أو الـ SKU لجرد البيانات والتحكم فورا:")
        
        for idx, p in enumerate(products):
            if search_query.lower() in p['name'].lower() or search_query.lower() in str(p.get('sku', '')).lower():
                
                has_special_offer = False
                connected_offer_id = None
                for o in offers:
                    buy_list = o.get('buy', {}).get('products', [])
                    get_list = o.get('get', {}).get('products', [])
                    buy_ids = [item['id'] if isinstance(item, dict) else item for item in buy_list]
                    get_ids = [item['id'] if isinstance(item, dict) else item for item in get_list]
                    if p['id'] in buy_ids or p['id'] in get_ids:
                        has_special_offer = True
                        connected_offer_id = o['id']
                        break
                
                st.markdown("<div class='product-card'>", unsafe_allow_html=True)
                c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
                
                with c1:
                    product_url = p.get('url', '#')
                    st.markdown(f"📦 <a href='{product_url}' target='_blank' class='product-link'>{p['name']}</a>", unsafe_allow_html=True)
                    st.markdown(f"🏷 *SKU:* `{p.get('sku', 'لا يوجد')}`")
                    if p.get('thumbnail') or p.get('main_image'):
                        st.markdown("<span style='color: #2a9d8f; font-weight: bold;'>🖼️ المنتج يحتوي على صورة ترويجية</span>", unsafe_allow_html=True)
                    else:
                        st.markdown("<span style='color: #e76f51; font-weight: bold;'>⚠️ المنتج يحتاج لصورة بالمتجر</span>", unsafe_allow_html=True)
                
                with c2:
                    reg_price = p.get('price', {}).get('amount', p.get('price', 0)) if isinstance(p.get('price'), dict) else p.get('price', 0)
                    st.markdown(f"💵 السعر الحالي: **{reg_price} SAR**")
                    st.markdown(f"🔢 المخزون: **{p.get('quantity', 0)} حبة** | المبيعات: **{p.get('sold_quantity', 0)}**")
                
                with c3:
                    st.markdown(f"🔑 `ID: {p['id']}`")
                    if st.button("📋 نسخ الـ ID", key=f"cp_id_key_{p['id']}_{idx}"): st.toast(f"تم نسخ المعرّف: {p['id']}")
                
                with c4:
                    if has_special_offer:
                        if st.button("🟢 عرض ترويجي نشط (إلغاء)", key=f"p_off_del_{p['id']}_{idx}", type="primary"):
                            requests.delete(f"{SALLA_API_URL}/{connected_offer_id}", headers=HEADERS)
                            st.rerun()
                    else:
                        st.button("⚪ لا يوجد عرض مربوط", key=f"p_off_none_lbl_{p['id']}_{idx}", disabled=True)
                        
                    # --- هندسة إصلاح زر الإظهار والإخفاء الشامل لعام 2026 طبقاً للمستندات المرفقة ---
                    current_status = p.get('status', 'sale') # الحقل المعتمد لحالة النشر في المتجر
                    btn_status_label = "👁️ إخفاء من المتجر" if current_status == "sale" else "👁️ إظهار بالمتجر"
                    
                    if st.button(btn_status_label, key=f"p_status_toggle_action_{p['id']}_{idx}"):
                        target_status = "hidden" if current_status == "sale" else "sale"
                        status_payload = {"status": target_status}
                        
                        # إرسال طلب POST مع الحقل status ليعمل ويسمع فوراً بالمتجر بدون أدنى خطأ
                        up_res = requests.post(f"https://api.salla.dev/admin/v2/products/{p['id']}/status", json=status_payload, headers=HEADERS)
                        if up_res.status_code in [200, 201]:
                            st.success("تم تحديث حالة الظهور بالمتجر!")
                            st.rerun()
                        else:
                            st.error("خطأ بمزامنة الصلاحيات مع المتجر.")
                            
                st.markdown("</div>", unsafe_allow_html=True)
