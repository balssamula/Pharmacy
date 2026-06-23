import streamlit as st

st.set_page_config(
    page_title="منظومة بلسم الرقمية لإدارة العروض",
    layout="wide",
    page_icon="🎁",
    initial_sidebar_state="expanded"
)

from offers_page import render_offers_page
from products_page import render_products_page

# =========================================================================
# CSS السحري والمطور لحل مشكلة تداخل نصوص الرموز (expand_more / arrow_down)
# =========================================================================
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
    
    /* تطبيق خط Cairo فقط على النصوص المكتوبة لمنع جبر الأيقونات على التحول لكلمات */
    html, body, [data-testid="stAppViewContainer"] p, 
    [data-testid="stAppViewContainer"] span, 
    [data-testid="stAppViewContainer"] h1, 
    [data-testid="stAppViewContainer"] h2, 
    [data-testid="stAppViewContainer"] h3, 
    [data-testid="stAppViewContainer"] h4, 
    [data-testid="stAppViewContainer"] h5, 
    [data-testid="stAppViewContainer"] h6, 
    [data-testid="stAppViewContainer"] label, 
    [data-testid="stAppViewContainer"] button, 
    [data-testid="stAppViewContainer"] input, 
    [data-testid="stAppViewContainer"] select {
        font-family: 'Cairo', sans-serif !important;
    }
    
    /* استثناء كامل وحاسم للأيقونات الداخلية لـ Streamlit للحفاظ على الخط الافتراضي لها */
    .stIcon, [data-testid="stIcon"], [class^="st-"] svg, .material-icons, i {
        font-family: inherit !important;
    }
    
    [data-testid="stSidebar"] { background-color: #0f1c2e !important; padding: 20px 15px !important; }
    [data-testid="stSidebar"] * { color: #ffffff !important; }
    .stButton button { border-radius: 8px !important; font-weight: 600 !important; }
    </style>
""", unsafe_allow_html=True)

if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if "access_token" not in st.session_state: st.session_state["access_token"] = ""
if "admin_password" not in st.session_state: st.session_state["admin_password"] = "admin123"

# بوابة الدخول الآمنة
if not st.session_state["logged_in"]:
    _, col2, _ = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h3 style='text-align:center;'>🏥 تسجيل الدخول - منظومة بلسم الرقمية</h3>", unsafe_allow_html=True)
        st.divider()
        token = st.text_input("🔑 مفتاح الربط (Access Token):", type="password")
        un = st.text_input("👤 اسم المستخدم:")
        pw = st.text_input("🔒 كلمة المرور:", type="password")
        if st.button("🚀 دخول آمن للمنظومة", use_container_width=True):
            if un == "admin" and pw == st.session_state["admin_password"] and token.strip():
                st.session_state["logged_in"] = True
                st.session_state["access_token"] = token.strip()
                st.rerun()
            else:
                st.error("❌ عذراً، تأكد من صحة البيانات والتوكن المرفق!")
    st.stop()

# ترويسة علوية
st.markdown("<h1 style='color:#0f1c2e;'>🏥 لوحة التحكم الإدارية لصيدليات بلسم العُلا</h1>", unsafe_allow_html=True)
st.markdown("---")

c_tok, c_pwd, _ = st.columns([2, 2, 4])
with c_tok:
    with st.popover("⚙️ إعدادات مفتاح الربط"):
        new_t = st.text_input("أدخل توكن الربط الجديد:", value=st.session_state["access_token"], type="password")
        if st.button("تأكيد تحديث التوكن"):
            st.session_state["access_token"] = new_t
            st.success("تم التحديث!")
            st.rerun()
with c_pwd:
    with st.popover("🔒 تعديل كلمة مرور النظام"):
        new_p = st.text_input("أدخل الباسورد الجديد:", type="password")
        if st.button("تأكيد حفظ الباسورد"):
            st.session_state["admin_password"] = new_p
            st.success("تم الحفظ بنجاح!")

st.divider()

# القائمة الجانبية مع زر تحديث البيانات والصفحة المطلوب
st.sidebar.markdown("### 🏪 أقسام المنظومة")
page = st.sidebar.radio(
    "انتقل بين الواجهات الفنية:",
    ["لوحة إدارة وتصفية العروض الحالية", "مركز جرد وفحص مستودع المنتجات"]
)

st.sidebar.divider()
# زر تحديث الصفحة البرمجي الفعلي المسترجع للعمل الفوري
if st.sidebar.button("🔄 تحديث البيانات والصفحة", use_container_width=True):
    st.rerun()

if st.sidebar.button("🚪 تسجيل الخروج من النظام", use_container_width=True):
    st.session_state["logged_in"] = False
    st.rerun()

# توجيه الصفحات الفعلي
if page == "لوحة إدارة وتصفية العروض الحالية":
    render_offers_page()
else:
    render_products_page()
