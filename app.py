import streamlit as st
from utils.database import init_database, fetch_user, update_last_access, get_user_permissions
from utils.helpers import get_branch_number

# تهيئة قاعدة البيانات
init_database()

st.set_page_config(
    page_title="نظام بلسم العلا - مطابقة الطلبات والفواتير",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 💡 [تم الإصلاح]: إغلاق وسم النص البرمجي الـ CSS المكسور لمنع الـ SyntaxError
st.markdown(
    """
    <style>
    /* إخفاء قسم روابط التنقل التلقائي في السايدبار */
    [data-testid="stSidebarNav"] {
        display: none !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# حقن الـ CSS المشترك والمنسق بالكامل
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@300;400;500;700;800&display=swap');
    * { font-family: 'Tajawal', sans-serif; }
    
    .hero {
        background: linear-gradient(135deg, #0f4c5c 0%, #1f7a8c 50%, #16425b 100%);
        border-radius: 24px;
        padding: 2rem;
        color: white;
        margin-bottom: 1rem;
        text-align: right;
    }
    .hero h1 { font-weight: 800; margin: 0 0 0.5rem 0; font-size: 2.2rem; color: white; }
    .hero p { margin: 0; font-size: 1.1rem; opacity: 0.9; }
    
    .section-title {
        font-size: 1.4rem;
        font-weight: 700;
        color: #16425b;
        margin: 1.5rem 0 1rem 0;
        border-right: 5px solid #1f7a8c;
        padding-right: 10px;
        text-align: right;
    }
    
    .note-card {
        background-color: #f8f9fa;
        border-right: 4px solid #1f7a8c;
        padding: 1rem;
        border-radius: 12px;
        margin-bottom: 1rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
        text-align: right;
    }
    
    div[data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 10px 15px;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.02);
        text-align: center;
    }
    div[data-testid="stMetricLabel"] {
        font-size: 0.9rem !important;
        color: #64748b !important;
        font-weight: 500;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.6rem !important;
        color: #0f4c5c !important;
        font-weight: 700;
    }
</style>
""", unsafe_allow_html=True)

# إدارة الجلسة (Session State)
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = None
if "user_role" not in st.session_state:
    st.session_state.user_role = None
if "pharmacist_name" not in st.session_state:
    st.session_state.pharmacist_name = None

# شاشة تسجيل الدخول
if not st.session_state.logged_in:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h2 style='text-align: center; color: #0f4c5c; margin-top: 2rem;'>🔐 تسجيل الدخول للنظام</h2>", unsafe_allow_html=True)
        with st.form("login_form"):
            username_input = st.text_input("👤 اسم المستخدم", placeholder="أدخل اسم المستخدم...")
            password_input = st.text_input("🔑 كلمة المرور", type="password", placeholder="أدخل كلمة المرور...")
            submit_login = st.form_submit_button("ورود إلى لوحة التحكم", use_container_width=True)
            
            if submit_login:
                user = fetch_user(username_input, password_input)
                if user:
                    st.session_state.logged_in = True
                    
                    # 💡 استخراج القيم القياسية من الـ Tuple الراجع من قاعدة البيانات
                    current_username = user[0]
                    current_role = user[2]
                    current_pharmacist_name = user[3] if len(user) > 3 else ""
                    
                    # حفظ البيانات في سياق الجلسة (Session State)
                    st.session_state.username = current_username
                    st.session_state.user_role = current_role
                    st.session_state.pharmacist_name = current_pharmacist_name
                    
                    # 💡 [تم الإصلاح]: تمرير المعاملين المطلوبين صراحةً للدالة (username و pharmacist_name)
                    update_last_access(current_username, current_pharmacist_name)
                    
                    st.success("👋 تم تسجيل الدخول بنجاح! جاري تحويلك...")
                    st.rerun()
                else:
                    st.error("❌ اسم المستخدم أو كلمة المرور غير صحيحة.")
else:
    # الحصول على الصلاحيات الحالية للمستخدم النشط
    permissions = get_user_permissions(st.session_state.username)
    
    with st.sidebar:
        st.markdown(f"### 🏥 مرحباً {st.session_state.username}")
        if st.session_state.pharmacist_name:
            st.markdown(f"👤 صيدلي: {st.session_state.pharmacist_name}")
            
        st.markdown("---")
        st.markdown("### 🛠️ التنقل بين الشاشات")
        
        # مصفوفة خيارات التنقل القياسية
        nav_options = ["📊 لوحة مطابقات التسويات المالية"]
        
        # حقن خيار العروض الخاصة المنفصل والمطلوب للإداره فقط حراً بالسايدبار
        if st.session_state.user_role in ["admin", "manager"]:
            nav_options.append("🎁 مركز إدارة العروض الخاصة (سلة)")
            nav_options.append("📦 تفصيلي المنتجات")       # 💡 إضافة الخيار ليظهر في السايدبار
            nav_options.append("📈 تحليل مبيعات الشهور") # 💡 إضافة الخيار ليظهر في السايدبار

        if permissions and permissions.get("can_manage_users"):
            nav_options.append("👥 إدارة صلاحيات المستخدمين")
        if permissions and permissions.get("can_view_balances"):
            nav_options.append("💰 تحديث ورفع الأرصدة")
        if permissions and permissions.get("can_view_monitoring"):
            nav_options.append("🖥️ شاشة المراقبة والنظام")
            
        app_mode = st.radio("اختر الوجهة الحالية:", nav_options, key="main_navigation_pane")
        st.markdown("---")
        
        if st.button("🚪 تسجيل الخروج", use_container_width=True, key="logout_sidebar_btn"):
            st.session_state.logged_in = False
            st.session_state.username = None
            st.session_state.user_role = None
            st.session_state.pharmacist_name = None
            st.rerun()

    # =========================================================================
    # 🧠 توجيه ومزامنة الصفحات بناءً على الخيار المحدد من السايدبار
    # =========================================================================
    if app_mode == "📊 لوحة مطابقات التسويات المالية":
        if st.session_state.user_role in ["admin", "manager"]:
            from pages import admin_dashboard
            admin_dashboard.show()
        else:
            from pages import pharmacy_dashboard
            pharmacy_dashboard.show()
            
    elif app_mode == "🎁 مركز إدارة العروض الخاصة (سلة)":
        from pages import admin_dashboard
        admin_dashboard.show_special_offers_page()
        
    elif app_mode == "👥 إدارة صلاحيات المستخدمين":
        from pages import users_management
        users_management.show()
        
    elif app_mode == "💰 تحديث ورفع الأرصدة":
        from pages import balances_updater
        balances_updater.show()
        
    elif app_mode == "🖥️ شاشة المراقبة والنظام":
        from pages import monitoring
        monitoring.show()
