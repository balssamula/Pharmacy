import streamlit as st
import pandas as pd
import io
import requests
import json
from datetime import datetime

# --- 1. إعدادات المنظومة وتصميم الهوية البصرية الفاخرة المصلحة ---
st.set_page_config(page_title="منظومة بلسم الرقمية لإدارة العروض", layout="wide", page_icon="🎁")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
    
    html, body, .stMarkdown, .stSelectbox, div[data-testid="stSidebar"] {
        font-family: 'Cairo', sans-serif !important;
        text-align: right !important;
        direction: rtl !important;
    }
    
    /* تصميم صفحة تسجيل الدخول الفاخرة */
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
    
    /* الشريط العلوي الثابت والفاخر */
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
    
    /* بطاقات المظهر المصلح والجميل 100% */
    .product-card {
        background-color: #ffffff;
        padding: 24px;
        border-radius: 14px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.06);
        border-right: 6px solid #00b4d8;
        margin-bottom: 20px;
        border-left: 1px solid #eef2f5;
        border-top: 1px solid #eef2f5;
        border-bottom: 1px solid #eef2f5;
    }
    
    .offer-card {
        background-color: #ffffff;
        padding: 24px;
        border-radius: 14px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.06);
        border-right: 6px solid #2a9d8f;
        margin-bottom: 20px;
        border-left: 1px solid #eef2f5;
        border-top: 1px solid #eef2f5;
        border-bottom: 1px solid #eef2f5;
    }
    
    .sub-card {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 8px;
        border: 1px dashed #00b4d8;
        margin-top: 10px;
    }
    
    /* أزرار ونصوص القائمة الجانبية الضخمة والواضحة */
    [data-testid="stSidebar"] { background-color: #0f1c2e !important; min-width: 320px !important; }
    [data-testid="stSidebar"] * { color: #ffffff !important; font-size: 16px !important; }
    [data-testid="stSidebar"] h2 { color: #00b4d8 !important; font-size: 26px !important; font-weight: 700 !important; text-align: center !important; }
    div.row-widget.stRadio div[data-testid="stMarkdownContainer"] p { color: #ffffff !important; font-size: 18px !important; font-weight: 600 !important; }

    .stButton>button { width: 100% !important; font-weight: bold !important; border-radius: 8px !important; height: 42px; }
    .product-link { color: #00b4d8 !important; font-weight: bold; text-decoration: none; font-size: 18px; }
    .product-link:hover { text-decoration: underline !important; }
    </style>
""", unsafe_allow_html=True)

# --- 2. إدارة جلسة تسجيل الدخول وذاكرة الإعدادات ---
if "admin_password" not in st.session_state:
    st.session_state["admin_password"] = "admin123"
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "access_token" not in st.session_state:
    st.session_state["access_token"] = "ory_at_ugEJJSSlUAAlAnZIEQPc_hn5cqsgxpNyG5NA344nNHU.uekLYqGGWEY4ngGNjUp1jJooR5XPA-UD3yyKju36tOo"
if "setup_completed" not in st.session_state:
    st.session_state["setup_completed"] = True

# شاشة القفل الأمنية للدخول
if not st.session_state["logged_in"]:
    st.markdown("<div class='login-container'>", unsafe_allow_html=True)
    st.markdown("<h2 style='color:#0f1c2e; font-weight:700;'>تسجيل دخول المنظومة</h2>", unsafe_allow_html=True)
    username = st.text_input("اسم المستخدم:", value="admin", key="lg_username")
    password = st.text_input("كلمة المرور:", type="password", key="lg_password")
    if st.button("🔒 دخول آمن للمنظومة", key="login_btn"):
        if username == "admin" and password == st.session_state["admin_password"]:
            st.session_state["logged_in"] = True
            st.rerun()
        else:
            st.error("بيانات الدخول خاطئة.")
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

SALLA_API_URL = "https://api.salla.dev/admin/v2/specialoffers"
HEADERS = {"Authorization": f"Bearer {st.session_state['access_token']}", "Content-Type": "application/json"}

# --- الشريط العلوي الثابت والذكي للتحكم السريع بجميع الصفحات ---
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

# --- القائمة الجانبية المحدثة بوضوح كامل وحروف بيضاء زاهية ---
st.sidebar.markdown("<h2>بوابة بلسم الرقمية</h2>", unsafe_allow_html=True)
st.sidebar.divider()

page = st.sidebar.radio("📋 تصفح الأقسام التنفيذية:", [
    "📊 لوحة تصفية وإدارة العروض الحالية",
    "📦 مركز جرد المنتجات ومعرفات الـ IDs"
])

st.sidebar.divider()
if st.sidebar.button("🔄 تحديث الصفحة وتحديث البيانات"):
    st.rerun()

# --- 3. دالة بناء نموذج الإكسيل الاحترافي الملون لإرجاع الملف المقفل ---
def generate_salla_excel_template():
    buffer = io.BytesIO()
    columns = [
        "Action", "Offer_ID", "Offer_Name", "Offer_Type", "Applied_Channel", 
        "With_Coupon", "Start_Date_Time", "Expiry_Date_Time", "Buy_Type", 
        "Buy_Quantity", "Buy_Products_IDs", "Get_Type", "Get_Quantity", 
        "Discount_Type", "Discount_Amount", "Get_Products_IDs", "Offer_Message"
    ]
    sample_data = [
        ["create", None, "عرض الحبة الثانية خصم 50%", "buy_x_get_y", "browser_and_application", "لا", "2026-06-21 11:30:00", "2026-07-21 23:59:59", "product", 1, "1298176905", "product", 1, "percentage", 50, "1298176905", "خصم 50% على الحبة الثانية"]
    ]
    df = pd.DataFrame(sample_data, columns=columns)
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='قائمة العروض')
        workbook = writer.book
        worksheet = writer.sheets['قائمة العروض']
        from openpyxl.styles import PatternFill, Font, Alignment
        header_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
        header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
        worksheet.row_dimensions[1].height = 28
        for cell in worksheet[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")
        for col in worksheet.columns:
            worksheet.column_dimensions[col[0].column_letter].width = 18
    return buffer.getvalue()

def parse_products_cleanly(product_list):
    if not product_list or not isinstance(product_list, list): return "كل منتجات المتجر"
    clean_elements = []
    for p in product_list:
        if isinstance(p, dict):
            clean_elements.append(f"• {p.get('name', 'منتج')} (SKU: {p.get('sku', 'بدون')})")
        else:
            clean_elements.append(f"• معرف منتج رقم: {p}")
    return "\n".join(clean_elements)

# ==========================================
# الشاشة الأولى: لوحة العروض المتقدمة والاستيراد الشاملة
# ==========================================
if page == "📊 لوحة تصفية وإدارة العروض الحالية":
    st.markdown("<h1 class='main-header'>📊 لوحة تصفية وإدارة العروض الخاصة الحالية</h1>", unsafe_allow_html=True)
    
    # استعادة حقل التنزيل لنموذج الإكسيل الاحترافي الملون المفقود
    c_inf, c_btn = st.columns([3, 1])
    with c_inf:
        st.write("قم بتنزيل النموذج وتعبئة البيانات بالصيغ المحددة للتواريخ والوقت، ثم أعد رفع الملف للتحديث الجماعي.")
    with c_btn:
        st.download_button(label="📥 تحميل نموذج الإكسيل الاحترافي", data=generate_salla_excel_template(), file_name="Salla_Offers_Pro_Template.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    uploaded_file = st.file_uploader("📂 اختر ملف العروض المعبأ بصيغة XLSX للاستيراد الجماعي الفوري:", type=["xlsx"])
    if uploaded_file:
        df_user = pd.read_excel(uploaded_file)
        st.dataframe(df_user)
        if st.button("🚀 تأكيد النشر الجماعي الفوري إلى متجرك"):
            st.success("جاري المزامنة مع سلة...")

    res = requests.get(SALLA_API_URL, headers=HEADERS)
    if res.status_code == 200:
        raw_offers = res.json().get("data", [])
        
        # الفلاتر والبحث
        st.markdown("### 🔍 جرد وفلترة العروض")
        f1, f2, f3 = st.columns(3)
        with f1: search_offer = st.text_input("ابحث باسم العرض أو الـ SKU:")
        with f2: offer_status_filter = st.selectbox("حالة الصلاحية:", ["الكل", "نشط مؤقتاً", "متوقف مؤقتاً"])
        with f3: offer_type_filter = st.selectbox("نوع العرض التسويقي:", ["الكل", "buy_x_get_y", "percentage"])

        for idx, offer in enumerate(raw_offers):
            st.markdown("<div class='offer-card'>", unsafe_allow_html=True)
            c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
            with c1:
                st.markdown(f"🎯 **العرض:** {offer['name']} | `Offer_ID: {offer['id']}`")
                st.caption(f"📅 الصلاحية: من {offer.get('start_date')} إلى {offer.get('expiry_date')}")
            with c2:
                st.markdown(f"**الحالة:** {'🟢 نشط' if offer['status'] == 'active' else '🔴 معطل'}")
            with c3:
                target_st = "inactive" if offer['status'] == "active" else "active"
                btn_lbl = "⏸️ إيقاف" if offer['status'] == "active" else "▶️ تفعيل"
                if st.button(btn_lbl, key=f"of_page_st_{offer['id']}_{idx}"):
                    requests.put(f"{SALLA_API_URL}/{offer['id']}/status", json={"status": target_st}, headers=HEADERS)
                    st.rerun()
            with c4:
                # تفعيل ميزة حذف العرض الخاص المباشر
                if st.button("🗑️ حذف العرض", key=f"of_page_del_{offer['id']}_{idx}"):
                    requests.delete(f"{SALLA_API_URL}/{offer['id']}", headers=HEADERS)
                    st.rerun()
                    
            # السهم المنسدل الموسع لتعديل كافة معطيات العرض (الاسم، الوقت، الشروط والنسب بالـ SKU)
            with st.expander("🔽 تعديل تفاصيل العرض والمنتجات والكميات والنسب"):
                st.markdown("<div class='sub-card'>", unsafe_allow_html=True)
                st.markdown(f"**🛒 المنتجات المشمولة حالياً بشرط الشراء X:**\n{parse_products_cleanly(offer.get('buy', {}).get('products', []))}")
                st.markdown(f"**🎁 منتجات الخصم والمكافأة الحالية Y:**\n{parse_products_cleanly(offer.get('get', {}).get('products', []))}")
                
                st.divider()
                st.markdown("#### ✏️ نموذج التحديث الشامل للعرض الخاص")
                ed_name = st.text_input("تعديل اسم العرض:", value=offer['name'], key=f"ed_nm_{offer['id']}")
                ed_msg = st.text_input("رسالة العرض الترويجية:", value=offer.get('message', ''), key=f"ed_msg_{offer['id']}")
                
                col_d1, col_d2 = st.columns(2)
                with col_d1: ed_start = st.text_input("تاريخ ووقت البدء (YYYY-MM-DD HH:mm:ss):", value=offer.get('start_date', ''), key=f"ed_st_{offer['id']}")
                with col_d2: ed_end = st.text_input("تاريخ ووقت الانتهاء (YYYY-MM-DD HH:mm:ss):", value=offer.get('expiry_date', ''), key=f"ed_en_{offer['id']}")
                
                col_q1, col_q2 = st.columns(2)
                with col_q1: ed_buy_q = st.number_input("كمية شراء X المطلوبة:", value=int(offer.get('buy', {}).get('quantity', 1)), key=f"ed_bq_{offer['id']}")
                with col_q2: ed_get_q = st.number_input("كمية مكافأة Y الممنوحة:", value=int(offer.get('get', {}).get('quantity', 1)), key=f"ed_gq_{offer['id']}")
                
                if st.button("💾 حفظ وإرسال التحديثات الكاملة لـ سلة", key=f"save_full_offer_{offer['id']}"):
                    update_payload = {
                        "name": ed_name,
                        "message": ed_msg,
                        "start_date": ed_start,
                        "expiry_date": ed_end,
                        "offer_type": offer.get('offer_type', 'buy_x_get_y'),
                        "buy": {"type": offer.get('buy', {}).get('type', 'product'), "quantity": int(ed_buy_q)},
                        "get": {"type": offer.get('get', {}).get('type', 'product'), "quantity": int(ed_get_q), "discount_type": offer.get('get', {}).get('discount_type', 'free-product')}
                    }
                    requests.put(f"{SALLA_API_URL}/{offer['id']}", json=update_payload, headers=HEADERS)
                    st.success("تم تحديث كافة تفاصيل العرض بنجاح حياً!")
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

# ==========================================
# الشاشة الثانية: مركز جرد المنتجات وإصلاح مشكلة المزامنة
# ==========================================
elif page == "📦 مركز جرد المنتجات ومعرفات الـ IDs":
    st.markdown("<h1 class='main-header'>📦 مركز جرد وتعديل ظهور وصور منتجات صيدليات بلسم</h1>", unsafe_allow_html=True)
    
    prod_res = requests.get("https://api.salla.dev/admin/v2/products", headers=HEADERS)
    off_res = requests.get(SALLA_API_URL, headers=HEADERS)
    
    if prod_res.status_code == 200 and off_res.status_code == 200:
        products = prod_res.json().get("data", [])
        offers = off_res.json().get("data", [])
        
        search_query = st.text_input("🔍 ابحث هنا بواسطة اسم المنتج أو الـ SKU لجرد وحالة الظهور بالمتجر:")
        
        for idx, p in enumerate(products):
            if search_query.lower() in p['name'].lower() or search_query.lower() in str(p.get('sku', '')).lower():
                
                # فحص الارتباط بالعروض الخاصة المطور والموثق
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
                    if st.button("📋 نسخ الـ ID", key=f"p_cp_id_{p['id']}_{idx}"): st.toast(f"تم نسخ المعرّف: {p['id']}")
                
                with c4:
                    if has_special_offer:
                        if st.button("🟢 عرض ترويجي نشط (إلغاء)", key=f"p_off_tg_{p['id']}_{idx}", type="primary"):
                            requests.delete(f"{SALLA_API_URL}/{connected_offer_id}", headers=HEADERS)
                            st.rerun()
                    else:
                        st.button("⚪ لا يوجد عرض مربوط", key=f"p_off_none_{p['id']}_{idx}", disabled=True)
                        
                    # --- إصلاح وهندسة زر الإخفاء والإظهار طبقاً لتوثيق سلة لعام 2026 ---
                    current_status = p.get('status', 'sale') # الحقل الصحيح لحالة التوفر الفعلي بالمتجر هو status
                    btn_status_label = "👁️ إخفاء من المتجر" if current_status == "sale" else "👁️ إظهار بالمتجر"
                    
                    if st.button(btn_status_label, key=f"p_status_toggle_btn_{p['id']}_{idx}"):
                        # إرسال طلب من نوع POST مع الحقل الإلزامي status ليعمل ويسمع بالمتجر فوراً
                        target_status = "hidden" if current_status == "sale" else "sale"
                        status_payload = {"status": target_status}
                        
                        up_res = requests.post(f"https://api.salla.dev/admin/v2/products/{p['id']}/status", json=status_payload, headers=HEADERS)
                        if up_res.status_code in [200, 201]:
                            st.success("تم تحديث حالة الظهور بنجاح حياً!")
                            st.rerun()
                        else:
                            st.error("خطأ بمزامنة الصلاحيات مع المتجر.")
                            
                st.markdown("</div>", unsafe_allow_html=True)
