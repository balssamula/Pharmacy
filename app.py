import streamlit as st
from utils.database import init_database, fetch_user, update_last_access, get_user_permissions

init_database()

st.set_page_config(page_title="نظام بلسم العلا", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@300;400;500;700;800&display=swap');
    * { font-family: 'Tajawal', sans-serif; }
    .hero { background: linear-gradient(135deg, #0f4c5c 0%, #1f7a8c 100%); border-radius: 24px; padding: 2rem; color: white; text-align: center; margin-bottom: 1rem; }
    .metric-box { background: white; border-radius: 18px; padding: 1rem; text-align: center; margin: 0.5rem; border: 1px solid #e6eef0; }
    .pill { display: inline-block; padding: 0.28rem 0.75rem; border-radius: 999px; font-size: 0.78rem; font-weight: 700; }
    .pill-blue { background: #dff1ff; color: #0f5488; }
    .pill-red { background: #ffe0df; color: #a32929; }
    .pill-amber { background: #fff0c2; color: #8a5b00; }
    .pill-slate { background: #eef3f5; color: #445b66; }
    .pill-completed { background: #28a745; color: white; }
    .stButton button { width: 100%; border-radius: 10px; }
    .note-card { background: #f4fbfc; border: 1px solid #d7ebef; border-radius: 16px; padding: 1rem; margin-bottom: 1rem; }
    .section-title { font-size: 1.15rem; font-weight: 800; color: #16425b; border-right: 5px solid #1f7a8c; padding-right: 0.65rem; margin: 1rem 0; }
    .session-card { background: #f8f9fa; border-radius: 12px; padding: 0.8rem; margin: 0.3rem 0; border-right: 3px solid #1f7a8c; }
</style>
""", unsafe_allow_html=True)

# Session State
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'username' not in st.session_state:
    st.session_state.username = ""
if 'user_role' not in st.session_state:
    st.session_state.user_role = ""
if 'pharmacist_name' not in st.session_state:
    st.session_state.pharmacist_name = ""
if 'page' not in st.session_state:
    st.session_state.page = "dashboard"

with st.sidebar:
    st.title("🌟 نظام بلسم العلا")
    st.markdown("---")
    
    if not st.session_state.logged_in:
        username = st.text_input("👤 اسم المستخدم")
        password = st.text_input("🔒 كلمة المرور", type="password")
        if st.button("🚪 دخول"):
            user = fetch_user(username, password)
            if user:
                st.session_state.logged_in = True
                st.session_state.username = user[0]
                st.session_state.user_role = user[1]
                st.session_state.pharmacist_name = user[2] or ""
                st.rerun()
            else:
                st.error("بيانات الدخول غير صحيحة")
    else:
        st.success(f"مرحباً {st.session_state.username}")
        
        if st.session_state.user_role == "pharmacy" and not st.session_state.pharmacist_name:
            name = st.text_input("👤 اسم الصيدلي")
            if st.button("💾 حفظ"):
                if name.strip():
                    st.session_state.pharmacist_name = name.strip()
                    update_last_access(st.session_state.username, st.session_state.pharmacist_name)
                    st.rerun()
        
        if st.session_state.user_role in ["admin", "manager"]:
            st.markdown("---")
            if st.button("📊 لوحة التحكم"):
                st.session_state.page = "dashboard"
                st.rerun()
            if st.button("🔄 تحديث الأرصدة"):
                st.session_state.page = "balances"
                st.rerun()
            if st.button("👥 مراقبة التعديلات"):
                st.session_state.page = "monitoring"
                st.rerun()
            if st.session_state.user_role == "admin":
                if st.button("👥 إدارة المستخدمين"):
                    st.session_state.page = "users"
                    st.rerun()
        
        st.markdown("---")
        if st.button("🚪 تسجيل خروج"):
            for key in ['logged_in', 'username', 'user_role', 'pharmacist_name', 'page']:
                st.session_state[key] = False if key == 'logged_in' else "dashboard"
            st.rerun()

# Main Content
if not st.session_state.logged_in:
    st.markdown("""
    <div class="hero">
        <h1>نظام بلسم العلا لمراقبة إدخالات الفواتير</h1>
        <p>نظام متكامل لمطابقة طلبات سلة والفواتير</p>
    </div>
    """, unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown('<div class="metric-box"><div style="font-size:1.5rem;font-weight:800;">17</div><div>🏥 فرع</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="metric-box"><div style="font-size:1.5rem;font-weight:800;">1000+</div><div>📦 طلب شهرياً</div></div>', unsafe_allow_html=True)
    with col3:
        st.markdown('<div class="metric-box"><div style="font-size:1.5rem;font-weight:800;">99%</div><div>⚡ دقة المطابقة</div></div>', unsafe_allow_html=True)
elif st.session_state.user_role == "pharmacy":
    if not st.session_state.pharmacist_name:
        st.info("👈 الرجاء إدخال اسم الصيدلي من القائمة الجانبية")
    else:
        from pages import pharmacy_dashboard
        pharmacy_dashboard.show()
else:
    if st.session_state.page == "users" and st.session_state.user_role == "admin":
        from pages import users_management
        users_management.show()
    elif st.session_state.page == "balances":
        from pages import balances_updater
        balances_updater.show()
    elif st.session_state.page == "monitoring":
        from pages import monitoring
        monitoring.show()
    else:
        from pages import admin_dashboard
        admin_dashboard.show()