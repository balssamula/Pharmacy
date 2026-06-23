import streamlit as st

st.set_page_config(
    page_title="منظومة بلسم الرقمية لإدارة العروض",
    layout="wide",
    page_icon="🎁",
    initial_sidebar_state="expanded"
)

from offers_page import render_offers_page
from products_page import render_products_page

# ==============================================================================================
# CSS الجذري والحاسم لتثبيت خط كايرو وحل تداخل الرموز + صباغة الأزرار المحددة بالأخضر الغامق والأبيض
# ==============================================================================================
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
    
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
    
    /* استثناء كامل وحاسم للأيقونات الافتراضية لمنع تداخل الكلمات البرمجية */
    .stIcon, [data-testid="stIcon"], [class^="st-"] svg, .material-icons, i, 
    [data-testid="stPopover"]::after, [data-testid="stExpander"]::after {
        font-family: inherit !important;
    }
    
    /* صباغة وتلوين أزرار التعديل، الإنشاء، وإعدادات النظام لتصبح باللون الأخضر الغامق والنص الأبيض المطلوب */
    div.stButton > button[data-testid="baseButton-primary"] {
        background-color: #0f5132 !important;
        color: #ffffff !important;
        border: 1px solid #0f5132 !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1) !important;
    }
    div.stButton > button[data-testid="baseButton-primary"]:hover {
        background-color: #146c43 !important;
        border-color: #146c43 !important;
        transform: scale(1.02) !important;
    }
    
    /* عزل وضمان بقاء أزرار الحذف باللون الأحمر لعدم التداخل الإداري */
    div.stButton > button[key*="t_dl_"] {
        background-color: #dc3545 !important;
        color: #ffffff !important;
        border: 1px solid #dc3545 !important;
    }
    
    [data-testid="stSidebar"] { background-color: #0f1c2e !important; padding: 20px 15px !important; }
    [data-testid="stSidebar"] * { color: #ffffff !important; }
    .stButton button { border-radius: 8px !important; font-weight: 600 !important; }
    </style>
""", unsafe_allow_html=True)

if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if "access_token" not in st.session_state: st.session_state["access_token"] = ""
if "admin_password" not in st.session_state: st.session_state["admin_password"] = "admin123"

if not st.session_state["logged_in"]:
    _, col2, _ = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h3 style='text-align:center;'>🏥 تسجيل الدخول - منظومة بلسم الرقمية</h3>", unsafe_allow_html=True)
        st.divider()
        token = st.text_input("🔑 مفتاح الربط (Access Token):", type="password")
        un = st.text_input("👤 اسم المستخدم:")
        pw = st.text_input("🔒 كلمة المرور:", type="password")
        if st.button("🚀 دخول آمن للمنظومة", use_container_width=True, type="primary"):
            if un == "admin" and pw == st.session_state["admin_password"] and token.strip():
                st.session_state["logged_in"] = True
                st.session_state["access_token"] = token.strip()
                st.rerun()
            else:
                st.error("❌ عذراً، تأكد من صحة البيانات والتوكن المرفق!")
    st.stop()

st.markdown("<h1 style='color:#0f1c2e;'>🏥 لوحة التحكم الإدارية لصيدليات بلسم العُلا</h1>", unsafe_allow_html=True)
st.markdown("---")

c_tok, c_pwd, _ = st.columns([2, 2, 4])
with c_tok:
    with st.popover("⚙️ إعدادات مفتاح الربط"):
        new_t = st.text_input("أدخل توكن الربط الجديد:", value=st.session_state["access_token"], type="password")
        if st.button("تحديث التوكن", type="primary", use_container_width=True):
            st.session_state["access_token"] = new_t
            st.success("تم التحديث!")
            st.rerun()
with c_pwd:
    with st.popover("🔒 تعديل كلمة مرور النظام"):
        new_p = st.text_input("أدخل الباسورد الجديد:", type="password")
        if st.button("حفظ الباسورد", type="primary", use_container_width=True):
            st.session_state["admin_password"] = new_p
            st.success("تم الحفظ بنجاح!")

st.divider()

st.sidebar.markdown("### 🏪 أقسام المنظومة")
page = st.sidebar.radio(
    "انتقل بين الواجهات الفنية:",
    ["لوحة إدارة وتصفية العروض الحالية", "مركز جرد وفحص مستودع المنتجات"]
)

st.sidebar.divider()
if st.sidebar.button("🔄 تحديث البيانات والصفحة فوراً", use_container_width=True):
    st.rerun()

if st.sidebar.button("🚪 تسجيل الخروج من النظام", use_container_width=True):
    st.session_state["logged_in"] = False
    st.rerun()

if page == "لوحة إدارة وتصفية العروض الحالية":
    render_offers_page()
else:
    render_products_page()
