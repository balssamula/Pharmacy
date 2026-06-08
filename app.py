import streamlit as st
from utils.database import init_database, fetch_user, update_last_access, get_user_permissions
from utils.helpers import get_branch_number

# تهيئة قاعدة البيانات عند الإقلاع
init_database()

st.set_page_config(
    page_title="نظام بلسم العلا - مطابقة الطلبات والفواتير",
    layout="wide",
    initial_sidebar_state="expanded",
)

# إخفاء روابط التنقل الافتراضية لـ Streamlit
st.markdown(
    """
    <style>
    [data-testid="stSidebarNav"] {
        display: none !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# حقن التنسيقات البصرية والـ CSS المشترك
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
    
    div[data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 10px 15px;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.02);
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# إدارة الجلسة الآمنة (Session State)
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = None
if "user_role" not in st.session_state:
    st.session_state.user_role = None
if "pharmacist_name" not in st.session_state:
    st.session_state.pharmacist_name = None

# دالة ذكية وصارمة لتحويل مدخلات قاعدة البيانات الملعوبة إلى قيم Boolean حقيقية
def parse_bool(val):
    if val in [True, 1, "1", "True", "true", "T", "t"]:
        return True
    return False

# 1️⃣ شاشة تسجيل الدخول
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
                    st.session_state.username = user[0]       
                    st.session_state.user_role = user[2]      
                    st.session_state.pharmacist_name = user[3] if len(user) > 3 else ""
                    
                    update_last_access(user[0], st.session_state.pharmacist_name)
                    st.success("👋 تم تسجيل الدخول بنجاح!")
                    st.rerun()
                else:
                    st.error("❌ اسم المستخدم أو كلمة المرور غير صحيحة.")
else:
    # 💡 تنظيف وتوحيد نصوص الأدوار وأسماء المستخدمين لضمان كسر حساسية الحروف
    u_role = str(st.session_state.user_role).strip().lower()
    u_name = str(st.session_state.username).strip().lower()

    # جلب الصلاحيات الفعلية من قاعدة البيانات وتحويلها بشكل صارم ومضمون
    permissions = get_user_permissions(st.session_state.username)
    
    can_view_dash = parse_bool(permissions.get("can_view_dashboard")) if permissions else False
    can_manage_users = parse_bool(permissions.get("can_manage_users")) if permissions else False
    can_view_balances = parse_bool(permissions.get("can_view_balances")) if permissions else False
    can_view_monitoring = parse_bool(permissions.get("can_view_monitoring")) if permissions else False

    # حماية وأوفررايد أمني مطلق لحساب الـ admin الرئيسي ليملك كافة الصلاحيات دائماً
    if u_role == "admin" or u_name == "admin":
        can_view_dash = True
        can_manage_users = True
        can_view_balances = True
        can_view_monitoring = True

    # 2️⃣ بناء القائمة الجانبية (Sidebar) الديناميكية المحصنة
    with st.sidebar:
        st.markdown(f"### 🏥 مرحباً بك: {st.session_state.username}")
        st.markdown(f"⚙️ الصلاحية النشطة: **{u_role.upper()}**")
        if st.session_state.pharmacist_name:
            st.markdown(f"👤 الاسم: {st.session_state.pharmacist_name}")
            
        st.markdown("---")
        st.markdown("### 🛠️ التنقل بين الشاشات والصفحات")
        
        nav_options = []
        
        if can_view_dash:
            nav_options.append("📊 لوحة مطابقات التسويات المالية")
            
        # 💡 [حماية مزدوجة]: التحقق من الدور أو اسم المستخدم لضمان ظهور الأزرار لـ admin و manager فوراً
        if u_role in ["admin", "manager"] or u_name in ["admin", "manager"]:
            nav_options.append("🎁 مركز إدارة العروض الخاصة (سلة)")
            nav_options.append("📦 تفصيلي وجرد المنتجات")
            nav_options.append("📈 تحليل مبيعات الشهور")
            
        if can_manage_users:
            nav_options.append("👥 إدارة صلاحيات المستخدمين")
            
        if can_view_balances:
            nav_options.append("💰 تحديث ورفع الأرصدة")
            
        if can_view_monitoring:
            nav_options.append("🖥️ شاشة المراقبة والنظام")
            
        # منع انهيار الواجهة في حال كانت المصفوفة فارغة لأي سبب
        if not nav_options:
            nav_options = ["📊 لوحة مطابقات التسويات المالية"]

        app_mode = st.radio("اختر الوجهة الحالية:", nav_options, key="main_navigation_pane")
        st.markdown("---")
        
        if st.button("🚪 تسجيل الخروج", use_container_width=True, key="logout_sidebar_btn"):
            st.session_state.logged_in = False
            st.session_state.username = None
            st.session_state.user_role = None
            st.session_state.pharmacist_name = None
            st.rerun()

    # =========================================================================
    # 3️⃣ توجيه ومزامنة الصفحات الفعلي بناءً على اختيار السايدبار النظيف
    # =========================================================================
    if app_mode == "📊 لوحة مطابقات التسويات المالية":
        if u_role in ["admin", "manager"] or u_name in ["admin", "manager"]:
            from pages import admin_dashboard
            admin_dashboard.show()
        else:
            from pages import pharmacy_dashboard
            pharmacy_dashboard.show()
            
    elif app_mode == "🎁 مركز إدارة العروض الخاصة (سلة)":
        from pages import admin_dashboard
        admin_dashboard.show_special_offers_page()
        
    elif app_mode == "📦 تفصيلي وجرد المنتجات":
        from pages import product_details
        product_details.show()
        
    elif app_mode == "📈 تحليل مبيعات الشهور":
        from pages import sales_analysis
        sales_analysis.show()
        
    elif app_mode == "👥 إدارة صلاحيات المستخدمين":
        from pages import users_management
        users_management.show()
        
    elif app_mode == "💰 تحديث ورفع الأرصدة":
        from pages import balances_updater
        balances_updater.show()
        
    elif app_mode == "🖥️ شاشة المراقبة والنظام":
        from pages import monitoring
        monitoring.show()
