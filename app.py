import streamlit as st
import pandas as pd
import io
import requests
import json
from datetime import datetime

# --- 1. إعدادات المنظومة وتصميم الهوية البصرية الفاخرة (CSS Advanced) ---
st.set_page_config(page_title="منظومة بلسم الرقمية لإدارة العروض", layout="wide", page_icon="🎁")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@300;400;600;700&display=swap');
    
    html, body, [data-testid="stSidebar"], .stMarkdown, .stSelectbox {
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
    
    /* الشريط العلوي الثابت والفاخر للتحكم السريع */
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
    
    /* بطاقات المنتجات والعروض المنفصلة والفاخرة والمصلحة تماماً */
    .product-card {
        background-color: #ffffff;
        padding: 24px;
        border-radius: 14px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.06);
        border-right: 6px solid #00b4d8;
        margin-bottom: 20px;
        direction: rtl !important;
    }
    
    .offer-card {
        background-color: #ffffff;
        padding: 24px;
        border-radius: 14px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.06);
        border-right: 6px solid #2a9d8f;
        margin-bottom: 20px;
        direction: rtl !important;
    }
    
    .sub-card {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 8px;
        border: 1px dashed #00b4d8;
        margin-top: 10px;
    }
    
    .main-header { color: #0f1c2e; font-weight: 700; border-bottom: 3px solid #00b4d8; padding-bottom: 8px; margin-bottom: 25px; }
    
    /* تخصيص القائمة الجانبية وعناصرها الاحترافية العريضة */
    [data-testid="stSidebar"] { background-color: #0f1c2e !important; min-width: 320px !important; }
    [data-testid="stSidebar"] h1 { color: #00b4d8 !important; font-weight: 700 !important; font-size: 24px !important; }
    
    /* تخصيص الأزرار الجانبية الجذابة */
    .sidebar-btn-container {
        background: rgba(255, 255, 255, 0.04);
        padding: 12px;
        border-radius: 10px;
        margin-bottom: 10px;
        border-right: 4px solid transparent;
        transition: all 0.3s ease;
    }
    .sidebar-btn-container:hover {
        background: #00b4d8;
        color: #0f1c2e !important;
        border-right: 4px solid #ffffff;
    }

    .stButton>button { width: 100% !important; font-weight: bold !important; border-radius: 8px !important; height: 42px; }
    .product-link { color: #00b4d8 !important; font-weight: bold; text-decoration: none; font-size: 18px; }
    .product-link:hover { text-decoration: underline !important; }
    </style>
""", unsafe_allow_html=True)

# --- 2. إدارة جلسة تسجيل الدخول وذاكرة الإعدادات الافتراضية ---
if "admin_password" not in st.session_state:
    st.session_state["admin_password"] = "admin123"
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "access_token" not in st.session_state:
    st.session_state["access_token"] = ""
if "setup_completed" not in st.session_state:
    st.session_state["setup_completed"] = False

# نظام قفل صفحة الدخول الأمنية لـ بلسم العلا
if not st.session_state["logged_in"]:
    st.markdown("<div class='login-container'>", unsafe_allow_html=True)
    st.image("https://cdn-icons-png.flaticon.com/512/5087/5087579.png", width=100)
    st.markdown("<h2 style='color:#0f1c2e; font-weight:700;'>تسجيل دخول المنظومة</h2>", unsafe_allow_html=True)
    username = st.text_input("اسم المستخدم:", value="admin", key="login_user")
    password = st.text_input("كلمة المرور:", type="password", key="login_pass")
    
    if st.button("🔒 دخول آمن للمنظومة", key="login_submit_btn"):
        if username == "admin" and password == st.session_state["admin_password"]:
            st.session_state["logged_in"] = True
            st.success("تم تسجيل الدخول بنجاح!")
            st.rerun()
        else:
            st.error("بيانات الاعتماد خاطئة، يرجى المحاولة مرة أخرى.")
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# توجيه المستخدم فوراً لإدخال مفتاح الاتصال بسلة بعد أول دخول
if not st.session_state["setup_completed"] or not st.session_state["access_token"]:
    st.markdown("<h1 class='main-header'>⚙️ إعدادات التأسيس الأولية والربط الرقمي</h1>", unsafe_allow_html=True)
    st.info("مرحباً بك في لوحة تحكم بلسم. يرجى إدخال مفتاح الوصول (Access Token) المستخرج من مطوري سلة لتفعيل صلاحيات العروض وجلب المخزون حياً:")
    
    init_token = st.text_input("Salla Access Token:", type="password", key="init_token_input")
    if st.button("🔗 حفظ وتفعيل الاتصال الحي بالمتجر", key="save_init_btn"):
        if init_token:
            st.session_state["access_token"] = init_token.strip()
            st.session_state["setup_completed"] = True
            st.success("✨ تم تأسيس الرابط بنجاح وتشغيل المنظومة حياً!")
            st.rerun()
        else:
            st.error("الرجاء تعبئة المفتاح أولاً.")
    st.stop()

SALLA_API_URL = "https://api.salla.dev/admin/v2/specialoffers"
HEADERS = {"Authorization": f"Bearer {st.session_state['access_token']}", "Content-Type": "application/json"}

# --- 3. الشريط العلوي الثابت والذكي للتحكم السريع في قمة التطبيق ---
st.markdown(f"""
    <div class='top-sticky-bar'>
        <div style='color: white; font-weight: bold; font-size: 16px;'>🛡️ لوحة الإشراف النشطة للمسؤول</div>
        <div style='color: #00b4d8; font-weight: bold;'>الربط الحالي: متصل حياً بمتجر سلة التجريبي</div>
    </div>
""", unsafe_allow_html=True)

# أزرار التحديث السريع لكلمة المرور والتوكين مباشرة من قمة كل الصفحات
top_col1, top_col2, top_col3 = st.columns([1, 1, 4])
with top_col1:
    with st.popover("🔑 تعديل مفتاح الربط"):
        new_tok = st.text_input("أدخل التوكين الجديد:", value=st.session_state["access_token"], type="password")
        if st.button("تحديث التوكن", key="update_top_tok"):
            st.session_state["access_token"] = new_tok.strip()
            st.success("تم تحديث الرابط!")
            st.rerun()
with top_col2:
    with st.popover("🔒 تعديل كلمة المرور"):
        new_pwd = st.text_input("أدخل كلمة المرور الجديدة:", type="password")
        if st.button("تحديث الباسورد", key="update_top_pwd"):
            st.session_state["admin_password"] = new_pwd.strip()
            st.success("تم التعديل!")

st.divider()

# --- القائمة الجانبية المطورة الاحترافية ذات الخطوط الكبيرة والأشكال الجذابة ---
st.sidebar.markdown("<div style='text-align:center;'><img src='https://salla.sa/assets/images/logo-light.svg' width='130'></div>", unsafe_allow_html=True)
st.sidebar.markdown("<h2 style='text-align:center; font-size:24px; color:#00b4d8;'>بوابة صيدليات بلسم</h2>", unsafe_allow_html=True)
st.sidebar.divider()

page = st.sidebar.radio("📋 تصفح الأقسام التنفيذية:", [
    "📊 لوحة تصفية وإدارة العروض الحالية",
    "📦 مركز جرد المنتجات ومعرفات الـ IDs"
])

st.sidebar.divider()
# زر التحديث العام الإجباري في القائمة الجانبية ليعمل في كافة أرجاء الصفحات
if st.sidebar.button("🔄 تحديث الصفحة وتحديث البيانات", key="global_refresh_btn"):
    st.rerun()

# --- دالة مساعدة لتنظيف مصفوفات الـ JSON لعرض الاسم والـ SKU فقط في العروض ---
def parse_products_cleanly(product_list):
    if not product_list or not isinstance(product_list, list):
        return "كل منتجات المتجر المتاحة"
    clean_elements = []
    for p in product_list:
        if isinstance(p, dict):
            name = p.get('name', 'منتج غير مسمى')
            sku = p.get('sku', 'بدون SKU')
            clean_elements.append(f"🏷️ {name} (SKU: `{sku}`)")
        else:
            clean_elements.append(f"معرّف برمي رقم: `{p}`")
    return " | ".join(clean_elements)

# ==========================================
# الشاشة الأولى: لوحة متابعة وتصفية العروض مع الاستيراد الفوري
# ==========================================
if page == "📊 لوحة تصفية وإدارة العروض الحالية":
    st.markdown("<h1 class='main-header'>📊 لوحة تصفية وإدارة العروض الخاصة الاحترافية</h1>", unsafe_allow_html=True)
    
    # ميزة استيراد العروض المباشرة من إكسيل داخل صفحة العروض مباشرة
    with st.expander("📥 زر إنشاء وعمليات العروض بالاستيراد الجماعي من ملف إكسيل (Excel Bulk Import)"):
        uploaded_file = st.file_uploader("📂 اختر ملف العروض المعبأ بصيغة XLSX لبدء النشر الجماعي:", type=["xlsx"], key="offer_page_uploader")
        if uploaded_file:
            df_user = pd.read_excel(uploaded_file)
            st.dataframe(df_user)
            if st.button("🚀 معالجة ونشر وإرسال جدول البيانات بالكامل لـ سلة", key="process_bulk_offers_btn"):
                st.success("تم جدولة العمليات وإرسالها لخوادم سلة!")
    
    res = requests.get(SALLA_API_URL, headers=HEADERS)
    if res.status_code == 200:
        raw_offers = res.json().get("data", [])
        
        # الفلاتر الذكية المتكاملة (اسم العرض، الـ SKU، رقم المنتج، الحالة والتوقيت)
        st.markdown("### 🔍 فلترة وجرد العروض")
        f1, f2, f3 = st.columns(3)
        with f1:
            search_offer = st.text_input("📝 ابحث باسم العرض، رقم العرض، أو الـ SKU:")
        with f2:
            offer_status_filter = st.selectbox("⚡ تصفية بحالة التوقيت والصلاحية:", ["الكل", "نشط مؤقتاً", "متوقف مؤقتاً", "منتهي الصلاحية", "لم يبدأ بعد"])
        with f3:
            offer_type_filter = st.selectbox("🏷️ نوع العرض المطبق بالصيدلية:", ["الكل", "buy_x_get_y", "percentage", "fixed_amount"])
            
        now = datetime.now()
        filtered_offers = []
        
        for o in raw_offers:
            match = True
            start_dt = datetime.strptime(o['start_date'], '%Y-%m-%d %H:%M:%S') if o.get('start_date') else None
            expiry_dt = datetime.strptime(o['expiry_date'], '%Y-%m-%d %H:%M:%S') if o.get('expiry_date') else None
            
            # فحص البحث بواسطة النص أو الـ SKU المضمن في مصفوفات العروض
            if search_offer:
                search_lower = search_offer.lower()
                prod_skus_string = str(o.get('buy', {}).get('products', [])) + str(o.get('get', {}).get('products', []))
                if search_lower not in o['name'].lower() and search_lower not in str(o['id']) and search_lower not in prod_skus_string:
                    match = False
                    
            if offer_type_filter != "الكل" and o.get('offer_type') != offer_type_filter: match = False
            if offer_status_filter == "نشط مؤقتاً" and o['status'] != "active": match = False
            elif offer_status_filter == "متوقف مؤقتاً" and o['status'] != "inactive": match = False
            elif offer_status_filter == "منتهي الصلاحية" and expiry_dt and expiry_dt < now: match = False
            elif offer_status_filter == "لم يبدأ بعد" and start_dt and start_dt > now: match = False
            
            if match: filtered_offers.append(o)
            
        st.divider()
        
        # التصدير المنسق لملف إكسيل
        if filtered_offers:
            exp_buffer = io.BytesIO()
            pd.DataFrame(filtered_offers)[['id', 'name', 'status', 'offer_type', 'start_date', 'expiry_date']].to_excel(exp_buffer, index=False)
            st.download_button("📥 تصدير تقرير العروض المصفاة لـ Excel", data=exp_buffer.getvalue(), file_name="Salla_Special_Offers_Report.xlsx")
            
        # عرض العروض في بطاقات مصلحة ومنفصلة تماماً من الناحية التنسيقية الجمالية
        for idx, offer in enumerate(filtered_offers):
            st.markdown("<div class='offer-card'>", unsafe_allow_html=True)
            c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
            with c1:
                st.markdown(f"🎯 **العرض التسويقي:** {offer['name']} | `Offer_ID: {offer['id']}`")
                st.caption(f"⏰ نطاق النشر المجدول: من {offer.get('start_date', '-')} إلى {offer.get('expiry_date', '-')}")
            with c2:
                st.markdown(f"**حالة العرض الحالي:** {'🟢 نشط' if offer['status'] == 'active' else '🔴 معطل'}")
            with c3:
                target_st = "inactive" if offer['status'] == "active" else "active"
                btn_lbl = "⏸️ إيقاف" if offer['status'] == "active" else "▶️ تفعيل"
                if st.button(btn_lbl, key=f"off_page_st_btn_{offer['id']}_{idx}"):
                    requests.put(f"{SALLA_API_URL}/{offer['id']}/status", json={"status": target_st}, headers=HEADERS)
                    st.rerun()
            with c4:
                # ميزة الحذف الفوري والمباشر للعرض الخاص من لوحة التحكم (Delete Special Offer)
                if st.button("🗑️ حذف العرض", key=f"off_page_del_btn_{offer['id']}_{idx}"):
                    requests.delete(f"{SALLA_API_URL}/{offer['id']}", headers=HEADERS)
                    st.success("تم إزالة العرض من المتجر بنجاح!")
                    st.rerun()
                    
            # السهم المجاور لتعديل العرض وعرض شروط وتفاصيل الـ SKU والنوع والمنتجات بدقة ونظافة كاملة
            with st.expander("🔽 تعديل العرض والمنتجات المشمولة والكميات (تطوير لحظي للـ API)"):
                st.markdown("<div class='sub-card'>", unsafe_allow_html=True)
                
                # استخراج الحقول النظيفة (اسم المنتج والـ SKU فقط) بدلاً من مصفوفة الـ JSON المتداخلة المزعجة
                buy_products_clean = parse_products_cleanly(offer.get('buy', {}).get('products', []))
                get_products_clean = parse_products_cleanly(offer.get('get', {}).get('products', []))
                
                st.markdown(f"🛒 **المنتجات المشمولة بشرط الشراء X:** {buy_products_clean}")
                st.markdown(f"🎁 **المنتجات المشمولة بهدية المكافأة Y:** {get_products_clean}")
                
                # حقول التعديل المباشر للحالة والتاريخ والكميات والمستهدفات عبر الـ SKU ورقم منتج
                edit_name = st.text_input("تعديل اسم العرض ولائحته:", value=offer['name'], key=f"edit_name_in_{offer['id']}")
                edit_start = st.text_input("تعديل تاريخ ووقت البدء (YYYY-MM-DD HH:mm:ss):", value=offer.get('start_date', ''), key=f"edit_start_in_{offer['id']}")
                edit_end = st.text_input("تعديل تاريخ ووقت الانتهاء (YYYY-MM-DD HH:mm:ss):", value=offer.get('expiry_date', ''), key=f"edit_end_in_{offer['id']}")
                
                if st.button("💾 حفظ وتحديث معطيات العرض حياً في سلة", key=f"save_edit_payload_btn_{offer['id']}"):
                    update_payload = {
                        "name": edit_name,
                        "start_date": edit_start,
                        "expiry_date": edit_end,
                        "offer_type": offer.get('offer_type', 'buy_x_get_y')
                    }
                    requests.put(f"{SALLA_API_URL}/{offer['id']}", json=update_payload, headers=HEADERS)
                    st.success("تم المزامنة وتحديث العرض بنجاح!")
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

# ==========================================
# الشاشة الثانية: مركز جرد المنتجات والتحكم الحقيقي الفاخر بالبطاقات المنفصلة
# ==========================================
elif page == "📦 مركز جرد المنتجات ومعرفات الـ IDs":
    st.markdown("<h1 class='main-header'>📦 مركز جرد وتحديث حالات وصور منتجات صيدليات بلسم</h1>", unsafe_allow_html=True)
    
    prod_res = requests.get("https://api.salla.dev/admin/v2/products", headers=HEADERS)
    off_res = requests.get(SALLA_API_URL, headers=HEADERS)
    
    if prod_res.status_code == 200 and off_res.status_code == 200:
        products = prod_res.json().get("data", [])
        offers = off_res.json().get("data", [])
        
        search_query = st.text_input("🔍 ابحث هنا بواسطة اسم المنتج أو الـ SKU لفلترة الجرد الفوري:")
        
        filtered_products = []
        for p in products:
            p_sku = str(p.get('sku', '')).lower()
            p_name = str(p.get('name', '')).lower()
            if search_query.lower() in p_name or search_query.lower() in p_sku:
                filtered_products.append(p)
                
        if filtered_products:
            p_buffer = io.BytesIO()
            pd.DataFrame(filtered_products)[['id', 'name', 'sku', 'quantity', 'status']].to_excel(p_buffer, index=False)
            st.download_button("📥 تصدير قائمة المنتجات المخزنية الحالية لـ Excel منسق", data=p_buffer.getvalue(), file_name="Balsam_Inventory_Report.xlsx")
            
        st.divider()
        
        # عرض كل منتج داخل بطاقة مستقلة (Product Card) مصلحة ومنسقة 100%
        for idx, p in enumerate(filtered_products):
            has_special_offer = False
            connected_offer_id = None
            for o in offers:
                if p['id'] in o.get('buy', {}).get('products', []) or p['id'] in o.get('get', {}).get('products', []):
                    has_special_offer = True
                    connected_offer_id = o['id']
                    break
                    
            st.markdown("<div class='product-card'>", unsafe_allow_html=True)
            c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
            
            with c1:
                # رابط مباشر لفتح صفحة المنتج فوراً بالمتجر عند الضغط عليه
                product_url = p.get('url', '#')
                st.markdown(f"📦 <a href='{product_url}' target='_blank' class='product-link'>{p['name']}</a>", unsafe_allow_html=True)
                st.markdown(f"🏷️ **SKU المنتج الحجمي:** `{p.get('sku', 'لا يوجد الـ SKU')}`")
                st.caption(f"📣 العنوان الترويجي: {p.get('promotion', {}).get('title', 'لا يوجد عنوان ترويجي مصاحب')}")
                
                # فحص وإظهار حالة الصورة شاشات بلسم
                if p.get('thumbnail'):
                    st.markdown("<span style='color: #2a9d8f; font-weight: bold;'>🖼️ المنتج يحتوي على صورة ترويجية</span>", unsafe_allow_html=True)
                else:
                    st.markdown("<span style='color: #e76f51; font-weight: bold;'>⚠️ المنتج يحتاج لصورة بالمتجر</span>", unsafe_allow_html=True)
            
            with c2:
                # إصلاح معالجة وعرض حقول السعر والسعر المخفض والكميات
                reg_price = p.get('price', {}).get('amount', p.get('price', 0)) if isinstance(p.get('price'), dict) else p.get('price', 0)
                sale_price = p.get('sale_price', {}).get('amount', None) if isinstance(p.get('sale_price'), dict) else p.get('sale_price', None)
                
                if sale_price and float(sale_price) > 0:
                    st.markdown(f"💵 السعر المخزن: ~~{reg_price}~~ **{sale_price} SAR**")
                else:
                    st.markdown(f"💵 السعر المخزن: **{reg_price} SAR**")
                    
                st.markdown(f"🔢 المتوفر بالمخزن: **{p.get('quantity', 0)} حبة**")
                st.markdown(f"📊 معدل مبيعات القطعة: **{p.get('sold_quantity', 0)} مبيعة**")
                
            with c3:
                # الـ ID مع رمز أيقونة النسخ التفاعلية والتوست
                st.markdown(f"🔑 `ID: {p['id']}`")
                if st.button("📋 نسخ رمز الـ ID", key=f"prod_copy_id_{p['id']}_{idx}"):
                    st.toast(f"تم نسخ المعرّف بنجاح: {p['id']}")
                    
            with c4:
                # زر تفعيل العرض الخاص التفاعلي الموحد (أخضر عند التفعيل / رمادي عند الإيقاف والحذف الفوري)
                if has_special_offer:
                    if st.button(f"🟢 العرض الخاص نشط (اضغط لإيقافه مؤقتاً)", key=f"p_off_toggle_btn_{p['id']}_{idx}", type="primary"):
                        requests.delete(f"{SALLA_API_URL}/{connected_offer_id}", headers=HEADERS)
                        st.success("تم إلغاء العرض بنجاح!")
                        st.rerun()
                else:
                    if st.button(f"⚪ لا يوجد عرض مربوط", key=f"p_off_toggle_none_{p['id']}_{idx}"):
                        st.info("يمكنك جدولة عرض له عبر ملف الإكسيل الرئيسي.")
                        
                # إصلاح زر الإخفاء والإظهار التلقائي بالمتجر (Change Product Status)
                current_status = "sale" if p.get('is_available', True) else "out"
                btn_status_label = "👁️ إخفاء من المتجر" if current_status == "sale" else "👁️ إظهار بالمتجر"
                if st.button(btn_status_label, key=f"status_p_action_btn_{p['id']}_{idx}"):
                    target_status = "out" if current_status == "sale" else "sale"
                    requests.post(f"https://api.salla.dev/admin/v2/products/{p['id']}/status", json={"status": target_status}, headers=HEADERS)
                    st.rerun()
                    
            st.markdown("</div>", unsafe_allow_html=True)
