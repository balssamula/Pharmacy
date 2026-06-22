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
    
    /* بطاقات المنتجات والعروض المنفصلة والفاخرة */
    .product-card {
        background-color: #ffffff;
        padding: 22px;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        border-right: 6px solid #00b4d8;
        margin-bottom: 20px;
        border-left: 1px solid #eef2f5;
        border-top: 1px solid #eef2f5;
        border-bottom: 1px solid #eef2f5;
    }
    
    .offer-card {
        background-color: #ffffff;
        padding: 22px;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        border-right: 6px solid #2a9d8f;
        margin-bottom: 20px;
    }
    
    .sub-card {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 8px;
        border: 1px dashed #00b4d8;
        margin-top: 10px;
    }
    
    .main-header { color: #0f1c2e; font-weight: 700; border-bottom: 3px solid #00b4d8; padding-bottom: 8px; margin-bottom: 25px; }
    
    /* تخصيص القائمة الجانبية وعناصرها */
    [data-testid="stSidebar"] { background-color: #0f1c2e !important; }
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] label { color: #00b4d8 !important; font-weight: 700 !important; }
    
    /* تصميم الأزرار التفاعلية */
    .stButton>button { width: 100% !important; font-weight: bold !important; border-radius: 8px !important; }
    .product-link { color: #00b4d8 !important; font-weight: bold; text-decoration: none; font-size: 18px; }
    .product-link:hover { text-decoration: underline !important; color: #0077b6 !important; }
    </style>
""", unsafe_allow_html=True)

# --- 2. إدارة جلسة تسجيل الدخول والأمان وكلمة المرور ---
if "admin_password" not in st.session_state:
    st.session_state["admin_password"] = "admin123"

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    st.markdown("<div class='login-container'>", unsafe_allow_html=True)
    st.image("https://cdn-icons-png.flaticon.com/512/5087/5087579.png", width=100)
    st.markdown("<h2 style='color:#0f1c2e; font-weight:700;'>تسجيل دخول المنظومة</h2>", unsafe_allow_html=True)
    
    username = st.text_input("اسم المستخدم:", value="admin")
    password = st.text_input("كلمة المرور:", type="password")
    
    if st.button("🔒 دخول آمن للمنظومة"):
        if username == "admin" and password == st.session_state["admin_password"]:
            st.session_state["logged_in"] = True
            st.success("تم تسجيل الدخول بنجاح!")
            st.rerun()
        else:
            st.error("بيانات الاعتماد خاطئة، يرجى المحاولة مرة أخرى.")
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# --- 3. تهيئة البيانات الأساسية وتوكن الربط ---
if "access_token" not in st.session_state:
    st.session_state["access_token"] = "ory_at_ugEJJSSlUAAlAnZIEQPc_hn5cqsgxpNyG5NA344nNHU.uekLYqGGWEY4ngGNjUp1jJooR5XPA-UD3yyKju36tOo"

SALLA_API_URL = "https://api.salla.dev/admin/v2/specialoffers"
HEADERS = {"Authorization": f"Bearer {st.session_state['access_token']}", "Content-Type": "application/json"}

# --- القائمة الجانبية المحدثة باحترافية كاملة ---
st.sidebar.markdown("<h1 style='text-align:center; font-size:24px; color:#00b4d8; margin-bottom:0;'>صيدليات بلسم العُلا</h1>", unsafe_allow_html=True)
st.sidebar.markdown("<p style='text-align:center; font-size:12px; margin-top:0; color:#a3b1c6;'>بوابة التحكم الذكية v2.5</p>", unsafe_allow_html=True)
st.sidebar.divider()

page = st.sidebar.radio("📋 تصفح أقسام المنظومة:", [
    "📊 لوحة متابعة وتصفية العروض",
    "📦 مركز جرد المنتجات والتحكم الحقيقي (IDs)",
    "⚙️ إعدادات الحساب والربط الرقمي"
])

# ==========================================
# الشاشة الأولى: لوحة متابعة وتصفية وتعديل العروض الحالية
# ==========================================
if page == "📊 لوحة متابعة وتصفية العروض":
    st.markdown("<h1 class='main-header'>📊 إدارة وتصفية العروض الخاصة الحالية</h1>", unsafe_allow_html=True)
    
    res = requests.get(SALLA_API_URL, headers=HEADERS)
    if res.status_code == 200:
        raw_offers = res.json().get("data", [])
        
        # أدوات البحث والتصفية المتقدمة للعروض
        st.markdown("### 🔍 أدوات الفلترة الذكية")
        f1, f2, f3 = st.columns(3)
        with f1:
            search_offer = st.text_input("📝 ابحث باسم العرض، رقم العرض، أو رقم المنتج:")
        with f2:
            offer_status_filter = st.selectbox("⚡ حالة العرض:", ["الكل", "نشط مؤقتاً", "متوقف مؤقتاً", "منتهي الصلاحية", "لم يبدأ بعد"])
        with f3:
            offer_type_filter = st.selectbox("🏷️ نوع العرض المطبق:", ["الكل", "buy_x_get_y", "percentage", "fixed_amount"])
            
        now = datetime.now()
        filtered_offers = []
        
        for o in raw_offers:
            match = True
            start_dt = datetime.strptime(o['start_date'], '%Y-%m-%d %H:%M:%S') if o.get('start_date') else None
            expiry_dt = datetime.strptime(o['expiry_date'], '%Y-%m-%d %H:%M:%S') if o.get('expiry_date') else None
            
            if search_offer and (search_offer.lower() not in o['name'].lower() and search_offer not in str(o['id'])):
                match = False
            if offer_type_filter != "الكل" and o.get('offer_type') != offer_type_filter:
                match = False
            if offer_status_filter == "نشط مؤقتاً" and o['status'] != "active": match = False
            elif offer_status_filter == "متوقف مؤقتاً" and o['status'] != "inactive": match_status = False
            elif offer_status_filter == "منتهي الصلاحية" and expiry_dt and expiry_dt < now: match = False
            elif offer_status_filter == "لم يبدأ بعد" and start_dt and start_dt > now: match = False
            
            if match: filtered_offers.append(o)
            
        # زر التصدير الاحترافي المنسق للعروض الخاصة لملف إكسيل
        st.divider()
        if filtered_offers:
            exp_buffer = io.BytesIO()
            pd.DataFrame(filtered_offers)[['id', 'name', 'status', 'offer_type', 'start_date', 'expiry_date']].to_excel(exp_buffer, index=False)
            st.download_button("📥 تصدير العروض الحالية المصفاة لـ Excel منسق", data=exp_buffer.getvalue(), file_name="Salla_Special_Offers_Report.xlsx")
            
        # عرض كل عرض في بطاقة (Card) منفصلة وأنيقة
        for idx, offer in enumerate(filtered_offers):
            st.markdown("<div class='offer-card'>", unsafe_allow_html=True)
            c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
            with c1:
                st.markdown(f"🎯 **العرض:** {offer['name']} | `Offer_ID: {offer['id']}`")
                st.caption(f"⏰ الصلاحية: من {offer.get('start_date', '-')} إلى {offer.get('expiry_date', '-')}")
            with c2:
                st.markdown(f"**الحالة:** {'🟢 نشط' if offer['status'] == 'active' else '🔴 معطل'}")
            with c3:
                target_st = "inactive" if offer['status'] == "active" else "active"
                btn_lbl = "⏸️ إيقاف" if offer['status'] == "active" else "▶️ تفعيل"
                if st.button(btn_lbl, key=f"off_btn_{offer['id']}_{idx}"):
                    requests.put(f"{SALLA_API_URL}/{offer['id']}/status", json={"status": target_st}, headers=HEADERS)
                    st.rerun()
            with c4:
                # زر تعديل العرض التفاعلي الجديد
                with st.popover("✏️ تعديل العرض"):
                    new_name = st.text_input("اسم العرض الجديد:", value=offer['name'])
                    if st.button("💾 حفظ التعديلات", key=f"save_edit_{offer['id']}"):
                        requests.put(f"{SALLA_API_URL}/{offer['id']}", json={"name": new_name}, headers=HEADERS)
                        st.success("تم تحديث اسم العرض بنجاح!")
                        st.rerun()
                        
            with st.expander("🔽 المنتجات والشروط المشمولة داخل هذا العرض"):
                st.markdown("<div class='sub-card'>", unsafe_allow_html=True)
                st.write(f"نوع العرض: `{offer.get('offer_type')}`")
                st.write(f"معرفات المنتجات المشمولة بالشراء: `{offer.get('buy', {}).get('products', 'الكل')}`")
                st.write(f"معرفات منتجات الخصم والمكافأة: `{offer.get('get', {}).get('products', 'نفس المنتج')}`")
                st.markdown("</div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

# ==========================================
# الشاشة الثانية: مركز جرد وتصفية واختصار المنتجات (IDs)
# ==========================================
elif page == "📦 مركز جرد المنتجات والتحكم الحقيقي (IDs)":
    st.markdown("<h1 class='main-header'>📦 مستعرض المنتجات وجرد الصلاحيات والعروض</h1>", unsafe_allow_html=True)
    
    prod_res = requests.get("https://api.salla.dev/admin/v2/products", headers=HEADERS)
    off_res = requests.get(SALLA_API_URL, headers=HEADERS)
    
    if prod_res.status_code == 200 and off_res.status_code == 200:
        products = prod_res.json().get("data", [])
        offers = off_res.json().get("data", [])
        
        # شريط بحث موحد يشمل الاسم و الـ SKU للمنتج
        search_query = st.text_input("🔍 ابحث هنا بواسطة اسم المنتج أو الـ SKU الخاص به لفلترة البيانات:")
        
        filtered_products = []
        for p in products:
            p_sku = str(p.get('sku', '')).lower()
            p_name = str(p.get('name', '')).lower()
            if search_query.lower() in p_name or search_query.lower() in p_sku:
                filtered_products.append(p)
                
        # زر التصدير الاحترافي المنسق للمنتجات إلى ملف إكسيل
        if filtered_products:
            p_buffer = io.BytesIO()
            pd.DataFrame(filtered_products)[['id', 'name', 'sku', 'quantity', 'status']].to_excel(p_buffer, index=False)
            st.download_button("📥 تصدير قائمة المنتجات الحالية لـ Excel منسق", data=p_buffer.getvalue(), file_name="Balsam_Products_Inventory.xlsx")
            
        st.divider()
        
        # عرض كل منتج داخل بطاقة منفصلة أنيقة (Card) بدلاً من الفواصل المستقيمة التقليدية
        for idx, p in enumerate(filtered_products):
            # فحص ارتباط المنتج بعرض خاص حالي
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
                # عند الضغط على اسم المنتج يتم فتح صفحة المنتج بالمتجر مباشرة في تبويب جديد
                product_url = p.get('url', '#')
                st.markdown(f"📦 <a href='{product_url}' target='_blank' class='product-link'>{p['name']}</a>", unsafe_allow_html=True)
                st.markdown(f"🏷️ **SKU:** `{p.get('sku', 'لا يوجد')}`")
                st.caption(f"📣 العنوان الترويجي: {p.get('promotion', {}).get('title', 'لا يوجد')}")
            
            with c2:
                # معالجة السعر والسعر المخفض والكميات برمجياً بشكل منسق تماماً
                reg_price = p.get('price', {}).get('amount', p.get('price', 0)) if isinstance(p.get('price'), dict) else p.get('price', 0)
                sale_price = p.get('sale_price', {}).get('amount', None) if isinstance(p.get('sale_price'), dict) else p.get('sale_price', None)
                
                if sale_price and float(sale_price) > 0:
                    st.markdown(f"💵 السعر: ~~{reg_price}~~ **{sale_price} SAR**")
                else:
                    st.markdown(f"💵 السعر: **{reg_price} SAR**")
                    
                st.markdown(f"🔢 المخزون: **{p.get('quantity', 0)} حبة** | المبيعات: **{p.get('sold_quantity', 0)}**")
                
            with c3:
                # أيقونة النسخ المباشر الذكية لرمز الـ ID بدلاً من النصوص الطويلة
                st.markdown(f"🔑 `ID: {p['id']}`")
                if st.button("📋 نسخ الـ ID", key=f"copy_id_{p['id']}_{idx}"):
                    st.toast(f"تم نسخ المعرّف: {p['id']}")
                    
            with c4:
                # زر تفاعلي موحد للعرض الخاص: أخضر عند التفعيل، ورمادي (Secondary) عند الإيقاف
                if has_special_offer:
                    if st.button("🟢 العرض الخاص نشط (إيقاف)", key=f"toggle_off_{p['id']}_{idx}", type="primary"):
                        requests.delete(f"{SALLA_API_URL}/{connected_offer_id}", headers=HEADERS)
                        st.success("تم إيقاف العرض الخاص بنجاح!")
                        st.rerun()
                else:
                    if st.button("⚪ لا يوجد عرض مربوط", key=f"toggle_on_{p['id']}_{idx}"):
                        st.info("يمكنك ربط هذا المنتج عبر شاشة رفع ملفات العروض المخصصة.")
                        
                # زر تعديل حالة توفر المنتج بالمتجر حياً
                current_status = "sale" if p.get('is_available', True) else "out"
                btn_status_label = "❌ تعطيل بالمتجر" if current_status == "sale" else "✅ تفعيل بالمتجر"
                if st.button(btn_status_label, key=f"status_p_btn_{p['id']}_{idx}"):
                    target_status = "out" if current_status == "sale" else "sale"
                    requests.post(f"https://api.salla.dev/admin/v2/products/{p['id']}/status", json={"status": target_status}, headers=HEADERS)
                    st.rerun()
                    
            st.markdown("</div>", unsafe_allow_html=True)

# ==========================================
# الشاشة الثالثة: إعدادات الحساب وتغيير كلمة المرور
# ==========================================
elif page == "⚙️ إعدادات الحساب والربط الرقمي":
    st.markdown("<h1 class='main-header'>⚙️ إعدادات الحساب والتحكم بالمنظومة</h1>", unsafe_allow_html=True)
    
    st.markdown("### 🔐 تعديل بيانات الأمان للوحة التحكم")
    new_pwd = st.text_input("كلمة المرور الجديدة للوحة التحكم:", type="password")
    if st.button("💾 تحديث كلمة المرور"):
        if new_pwd:
            st.session_state["admin_password"] = new_pwd.strip()
            st.success("تم تحديث كلمة المرور بنجاح! سيتم اعتمادها في عمليات تسجيل الدخول القادمة.")
        else:
            st.error("الرجاء إدخال كلمة مرور صالحة.")
            
    st.divider()
    st.markdown("### 🛠️ مفتاح الاتصال الحي بـ سلة (Access Token)")
    input_token = st.text_input("Salla Access Token:", value=st.session_state["access_token"], type="password")
    if st.button("🔗 تحديث رمز الربط"):
        st.session_state["access_token"] = input_token.strip()
        st.success("تم تحديث رمز الربط بنجاح!")
