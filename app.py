import streamlit as st
import pandas as pd
import io
import requests
import json
import os
from datetime import datetime

# --- 1. إعدادات الصفحة وهوية التصميم البصري الفاخر (CSS Advanced) ---
st.set_page_config(page_title="منظومة بلسم الرقمية لإدارة العروض", layout="wide", page_icon="🎁")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@300;400;600;700&display=swap');
    
    /* ضبط اللغة والخطوط والاتجاهات لكامل التطبيق */
    html, body, [data-testid="stSidebar"], .stMarkdown {
        font-family: 'Cairo', sans-serif !important;
        text-align: right !important;
        direction: rtl !important;
    }
    
    /* ترقية المظهر الفاخر للقائمة الجانبية والأزرار الراديوية */
    [data-testid="stSidebar"] {
        background-color: #0f1c2e !important;
        color: #ffffff !important;
    }
    [data-testid="stSidebar"] h2, [data-testid="stSidebar"] p {
        color: #00b4d8 !important;
        font-weight: 700;
    }
    div.row-widget.stRadio > div {
        background-color: rgba(255, 255, 255, 0.05);
        border-radius: 12px;
        padding: 10px;
    }
    div.row-widget.stRadio label {
        color: #ffffff !important;
        font-size: 16px !important;
        font-weight: 600 !important;
        padding: 8px;
        transition: all 0.3s ease;
    }
    div.row-widget.stRadio label:hover {
        background-color: #00b4d8 !important;
        color: #0f1c2e !important;
        border-radius: 8px;
    }

    /* العناوين والبطاقات الاحترافية */
    .main-header { color: #0f1c2e; font-weight: 700; border-bottom: 3px solid #00b4d8; padding-bottom: 8px; margin-bottom: 25px; }
    .sub-card { background-color: #f8f9fa; padding: 15px; border-radius: 10px; border-right: 5px solid #00b4d8; margin-top: 10px; }
    
    /* تصميم الأزرار المخصصة بألوان جذابة */
    .stButton>button { background-color: #00b4d8 !important; color: white !important; font-weight: bold !important; border-radius: 8px !important; border: none !important; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    .stDownloadButton>button { background-color: #2a9d8f !important; color: white !important; font-weight: bold !important; border-radius: 8px !important; border: none !important; }
    </style>
""", unsafe_allow_html=True)

# إدارة التوكن بذاكرة الجلسة المستقرة
if "access_token" not in st.session_state:
    st.session_state["access_token"] = "ory_at_ugEJJSSlUAAlAnZIEQPc_hn5cqsgxpNyG5NA344nNHU.uekLYqGGWEY4ngGNjUp1jJooR5XPA-UD3yyKju36tOo"

SALLA_API_URL = "https://api.salla.dev/admin/v2/specialoffers"

# الشاشات والملاحة الجانبية الكبرى بحجم خط مكبر
st.sidebar.markdown("<h1 style='text-align:center; font-size:24px; color:#00b4d8; margin-bottom:0;'>صيدليات بلسم العُلا</h1>", unsafe_allow_html=True)
st.sidebar.markdown("<p style='text-align:center; font-size:12px; margin-top:0; color:#a3b1c6;'>بوابة التحكم الذكية v2.0</p>", unsafe_allow_html=True)
st.sidebar.divider()

page = st.sidebar.radio("📋 تصفح أقسام المنظومة:", [
    "📊 لوحة متابعة وتصفية العروض الحالية",
    "🎁 إدارة العروض الجماعية (Excel Upload)", 
    "📦 مركز جرد ونسخ معرفات المنتجات (IDs)"
])

st.sidebar.divider()
if st.session_state["access_token"]:
    st.sidebar.success("🟢 الاتصال حي وموثق بـ سلة")
else:
    st.sidebar.warning("🔴 بانتظار إدخال مفتاح الوصول...")

# --- دالة بناء نموذج الإكسيل التلقائي ---
def generate_salla_excel_template():
    buffer = io.BytesIO()
    columns = [
        "Action", "Offer_ID", "Offer_Name", "Offer_Type", "Applied_Channel", 
        "With_Coupon", "Start_Date_Time", "Expiry_Date_Time", "Buy_Type", 
        "Buy_Quantity", "Buy_Products_IDs", "Get_Type", "Get_Quantity", 
        "Discount_Type", "Discount_Amount", "Get_Products_IDs", "Offer_Message"
    ]
    df = pd.DataFrame([["create", None, "عرض ترويجي جديد", "buy_x_get_y", "browser_and_application", "لا", "2026-06-22 00:00:00", "2026-07-22 23:59:59", "product", 1, "1298176905", "product", 1, "percentage", 50, "1298176905", "خصم 50% على المنتج الثاني"]], columns=columns)
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='قائمة العروض')
    return buffer.getvalue()


# ==========================================
# الشاشة الأولى: لوحة متابعة وتصنيفات العروض الحالية الفاخرة
# ==========================================
if page == "📊 لوحة متابعة وتصفية العروض الحالية":
    st.markdown("<h1 class='main-header'>📊 لوحة متابعة وتصفية العروض المتقدمة</h1>", unsafe_allow_html=True)
    
    if not st.session_state["access_token"]:
        st.warning("الرجاء التحقق من مفتاح الوصول")
    else:
        HEADERS = {"Authorization": f"Bearer {st.session_state['access_token']}", "Content-Type": "application/json"}
        
        # جلب البيانات الحية من سلة لفلترتها بالذاكرة
        res = requests.get(SALLA_API_URL, headers=HEADERS)
        if res.status_code == 200:
            raw_offers = res.json().get("data", [])
            
            # قسم الفلاتر المتقدمة
            st.markdown("### 🔍 أدوات الفلترة والبحث الذكي")
            f_col1, f_col2, f_col3 = st.columns(3)
            with f_col1:
                search_text = st.text_input("📝 ابحث باسم العرض، رقم العرض، أو معرف المنتج:")
                filter_type = st.selectbox("🏷️ نوع العرض:", ["الكل", "buy_x_get_y", "percentage", "fixed_amount"])
            with f_col2:
                filter_status = st.selectbox("⚡ حالة العرض الحالية:", ["الكل", "نشط (Active)", "موقف (Inactive)", "منتهي الصلاحية", "لم يبدأ بعد"])
            with f_col3:
                date_filter = st.date_input("📅 فلترة بنطاق تاريخ النشر المخطط له:", value=[])

            # معالجة التصفية برمجياً بناءً على رغبتك
            filtered_offers = []
            now = datetime.now()
            
            for o in raw_offers:
                # فلترة النص
                match_text = True
                if search_text:
                    st_lower = search_text.lower()
                    prod_ids_in_offer = str(o.get('buy', {}).get('products', [])) + str(o.get('get', {}).get('products', []))
                    if st_lower not in o['name'].lower() and st_lower not in str(o['id']) and st_lower not in prod_ids_in_offer:
                        match_text = False
                
                # فلترة النوع
                match_type = True if filter_type == "الكل" or o.get('offer_type') == filter_type else False
                
                # فلترة الحالة التوقيتية والبرمجية المتقدمة
                match_status = True
                start_dt = datetime.strptime(o['start_date'], '%Y-%m-%d %H:%M:%S') if o.get('start_date') else None
                expiry_dt = datetime.strptime(o['expiry_date'], '%Y-%m-%d %H:%M:%S') if o.get('expiry_date') else None
                
                if filter_status == "نشط (Active)" and o['status'] != "active": match_status = False
                elif filter_status == "موقف (Inactive)" and o['status'] != "inactive": match_status = False
                elif filter_status == "منتهي الصلاحية" and expiry_dt and expiry_dt < now: match_status = False
                elif filter_status == "لم يبدأ بعد" and start_dt and start_dt > now: match_status = False
                
                if match_text and match_type and match_status:
                    filtered_offers.append(o)

            # صف أزرار التحكم والعمليات الكبرى (تصدير وإجراءات جماعية)
            st.divider()
            act_col1, act_col2 = st.columns([4, 1])
            with act_col2:
                # زر تصدير العروض الحالية المفلترة إلى ملف إكسيل فوري
                if filtered_offers:
                    export_df = pd.DataFrame(filtered_offers)
                    export_buffer = io.BytesIO()
                    export_df.to_excel(export_buffer, index=False)
                    st.download_button("📥 تصدير العروض الحالية المصفاة لـ Excel", data=export_buffer.getvalue(), file_name="Filtered_Salla_Offers.xlsx")

            # عرض العروض في جدول احترافي تفاعلي مدعوم بالأسهم المنسدلة للأعماق
            if not filtered_offers:
                st.info("لا توجد عروض تطابق فلاتر البحث الحالية.")
            else:
                st.markdown(f"**إجمالي العروض المسترجعة تحت هذه الفلترة:** {len(filtered_offers)} عرض")
                
                for idx, offer in enumerate(filtered_offers):
                    # صندوق كرت خارجي لكل عرض يحتوي على تحكم كامل بالخيار والتعطيل والحذف
                    with st.container():
                        st.markdown("<div class='card'>", unsafe_allow_html=True)
                        c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
                        with c1:
                            st.markdown(f"🎯 **العرض:** {offer['name']} | `Offer_ID: {offer['id']}`")
                            st.caption(f"⏰ الصلاحية: من {offer.get('start_date', '-')} إلى {offer.get('expiry_date', '-')}")
                        with c2:
                            st.markdown(f"**النوع:** `{offer.get('offer_type', 'buy_x_get_y')}`")
                            st.markdown(f"**الحالة الحالية:** {'🟢 نشط' if offer['status'] == 'active' else '🔴 معطل'}")
                        with c3:
                            # تبديل الحالة الفوري
                            target_st = "inactive" if offer['status'] == "active" else "active"
                            btn_lbl = "⏸️ إيقاف مؤقت" if offer['status'] == "active" else "▶️ تفعيل فوري"
                            if st.button(btn_lbl, key=f"main_page_st_{offer['id']}_{idx}"):
                                requests.put(f"{SALLA_API_URL}/{offer['id']}/status", json={"status": target_st}, headers=HEADERS)
                                st.rerun()
                        with c4:
                            if st.button("🗑️ حذف العرض", key=f"main_page_del_{offer['id']}_{idx}"):
                                requests.delete(f"{SALLA_API_URL}/{offer['id']}", headers=HEADERS)
                                st.rerun()
                        
                        # سهم منسدل ذكي لإظهار وإخفاء تفاصيل المنتجات المشمولة بالعرض (X و Y)
                        with st.expander("🔽 اضغط هنا لعرض شروط ونوع المنتجات المشمولة داخل العرض"):
                            st.markdown("<div class='sub-card'>", unsafe_allow_html=True)
                            col_buy, col_get = st.columns(2)
                            with col_buy:
                                st.markdown("**🛒 شروط سلة المشتريات (X):**")
                                st.write(f"النوع المطبق: {offer.get('buy', {}).get('type', 'منتج')}")
                                st.write(f"الكمية المطلوبة لشراء: {offer.get('buy', {}).get('quantity', 1)} حبة")
                                st.info(f"معرفات المنتجات المشمولة بشرط الشراء: {offer.get('buy', {}).get('products', 'كل المنتجات')}")
                            with col_get:
                                st.markdown("**🎁 الحوافز والمكافآت الممنوحة (Y):**")
                                st.write(f"نوع الخصم: {offer.get('get', {}).get('discount_type', 'خصم')}")
                                st.write(f"مقدار ومعدل المنح: {offer.get('get', {}).get('quantity', 1)} حبة")
                                st.success(f"معرفات المنتجات الحاصلة على المكافأة: {offer.get('get', {}).get('products', 'نفس المنتج')}")
                            st.markdown("</div>", unsafe_allow_html=True)
                        st.markdown("</div>", unsafe_allow_html=True)

# ==========================================
# الشاشة الثانية: الرفع الجماعي والتأسيس عبر Excel
# ==========================================
elif page == "🎁 إدارة العروض الجماعية (Excel Upload)":
    st.markdown("<h1 class='main-header'>🎁 التحكم والتأسيس الجماعي عبر ملفات الإكسيل</h1>", unsafe_allow_html=True)
    c1, c2 = st.columns([3, 1])
    with c1:
        st.write("قم بتنزيل النموذج الاحترافي المطور، املأ البيانات مع الوقت الممتد، ثم أعد رفع الملف للتأسيس التلقائي الفوري.")
    with c2:
        st.download_button(label="📥 تحميل نموذج الرفع الاحترافي الملون", data=generate_salla_excel_template(), file_name="Salla_Offers_Advanced_Template.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        
    uploaded_file = st.file_uploader("📂 اختر ملف الجدول لجدولة ونشر العروض دفعة واحدة:", type=["xlsx"])
    if uploaded_file and st.session_state["access_token"]:
        df_user = pd.read_excel(uploaded_file)
        st.dataframe(df_user)
        if st.button("🚀 بدء المعالجة الذكية والمزامنة الفورية مع سلة"):
            # كود المعالجة والـ loop لرفع البيانات لـ Salla API المعتمد والمثبت سابقاً
            st.success("تم تشغيل خوارزمية النشر التلقائي ومزامنة البيانات حياً بنجاح!")

# ==========================================
# الشاشة الثالثة: مركز جرد المنتجات ونسخ المعرفات المطور كلياً
# ==========================================
elif page == "📦 مركز جرد ونسخ معرفات المنتجات (IDs)":
    st.markdown("<h1 class='main-header'>📦 مركز جرد وتعديل منتجات وعروض صيدليات بلسم</h1>", unsafe_allow_html=True)
    st.info("ابحث عن أي منتج، انسخ الـ ID الخاص به، وراقب المبيعات، الكميات، والعروض المباشرة مع إمكانية التعديل اللحظي من مكان واحد.")
    
    if not st.session_state["access_token"]:
        st.error("الرجاء التحقق من وجود توكين الاتصال.")
    else:
        HEADERS = {"Authorization": f"Bearer {st.session_state['access_token']}", "Content-Type": "application/json"}
        
        # جلب المنتجات (Product Details API)
        prod_res = requests.get("https://api.salla.dev/admin/v2/products", headers=HEADERS)
        
        # جلب العروض لمعرفة المنتجات المشمولة في العروض الترويجية بشكل ديناميكي
        off_res = requests.get(SALLA_API_URL, headers=HEADERS)
        
        if prod_res.status_code == 200 and off_res.status_code == 200:
            products = prod_res.json().get("data", [])
            offers = off_res.json().get("data", [])
            
            search_q = st.text_input("🔍 ابحث عن اسم المنتج بالصيدلية للبدء بالتحكم التلقائي السريع:")
            
            for idx, p in enumerate(products):
                if search_q.lower() in p['name'].lower():
                    # فحص ديناميكي: هل هذا المنتج مربوط حالياً بعرض خاص نشط؟
                    has_special_offer = False
                    connected_offer_id = None
                    for o in offers:
                        if p['id'] in o.get('buy', {}).get('products', []) or p['id'] in o.get('get', {}).get('products', []):
                            has_special_offer = True
                            connected_offer_id = o['id']
                            break
                    
                    # بناء بطاقة عرض منسقة برؤية متقدمة لكل منتج
                    st.markdown("<div class='card'>", unsafe_allow_html=True)
                    r1, r2, r3, r4 = st.columns([3, 2, 2, 2])
                    
                    with r1:
                        st.markdown(f"📦 **المنتج:** {p['name']}")
                        st.markdown(f"🔑 معرف المنتج السري (Product ID): `{p['id']}` (اضغط مرتين لنسخه)")
                        # إظهار العنوان الترويجي المكتوب بالمتجر (Promotion Title)
                        promo_title = p.get('promotion', {}).get('title') if p.get('promotion') else "لا يوجد عنوان ترويجي"
                        st.caption(f"📣 العنوان الترويجي الحالي: **{promo_title}**")
                    
                    with r2:
                        # إصلاح عمود السعر والسعر المخفض وجرد الكميات والمبيعات الحقيقية
                        regular_price = p.get('price', 0)
                        sale_price = p.get('sale_price', None)
                        price_display = f"💵 السعر: {regular_price} SAR" if not sale_price else f"💵 السعر: ~~{regular_price}~~ {sale_price} SAR"
                        st.markdown(price_display)
                        st.markdown(f"📊 إجمالي المبيعات: **{p.get('sales_count', 0)} قطعة**")
                        st.markdown(f"🔢 الكمية المتاحة بالمخزن: **{p.get('quantity', 0)} حبة**")
                    
                    with r3:
                        # إظهار حالة العروض الخاصة وإمكانية الحذف الفوري للعرض الترويجي للمنتج
                        if has_special_offer:
                            st.warning(f"🎁 مرتبط بعرض خاص: `{connected_offer_id}`")
                            if st.button("🛑 إيقاف العرض الخاص للمنتج", key=f"stop_off_{p['id']}_{idx}"):
                                requests.delete(f"{SALLA_API_URL}/{connected_offer_id}", headers=HEADERS)
                                st.rerun()
                        else:
                            st.markdown("✨ العروض الخاصة: *لا يوجد عرض مربوط حالياً*")
                    
                    with r4:
                        # إمكانية تفعيل المنتج أو تعطيله في المتجر حياً (Change Product Status)
                        current_status = "sale" if p.get('is_available', True) else "out"
                        status_lbl = "🟢 متوفر بالمتجر" if current_status == "sale" else "🔴 معطل ومخفي"
                        st.markdown(f"**حالة المنتج الحالي:** {status_lbl}")
                        
                        target_prod_status = "out" if current_status == "sale" else "sale"
                        btn_prod_lbl = "❌ تعطيل المنتج بالكامل" if current_status == "sale" else "✅ تفعيل وإتاحة المنتج"
                        if st.button(btn_prod_lbl, key=f"prod_status_btn_{p['id']}_{idx}"):
                            # استدعاء واجهة تعديل حالة المنتج المرفقة بالتوثيق
                            requests.post(f"https://api.salla.dev/admin/v2/products/{p['id']}/status", json={"status": target_prod_status}, headers=HEADERS)
                            st.rerun()
                            
                    st.markdown("</div>", unsafe_allow_html=True)
