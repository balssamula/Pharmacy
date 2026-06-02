import streamlit as st
import pandas as pd
from utils.database import get_all_users, add_user, delete_user, update_user_permissions, get_user_permissions

def show():
    st.markdown(
        """
        <div class="hero">
            <h1>👥 إدارة المستخدمين والصلاحيات</h1>
            <p>إضافة وتعديل وحذف المستخدمين وتحديد صلاحياتهم</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    # إضافة مستخدم جديد
    with st.expander("➕ إضافة مستخدم جديد", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            new_username = st.text_input("اسم المستخدم")
            new_password = st.text_input("كلمة المرور", type="password")
        with col2:
            new_role = st.selectbox("نوع المستخدم", ["pharmacy", "admin"])
            new_pharmacist_name = st.text_input("اسم الصيدلي (للفروع فقط)")
        
        if st.button("إضافة مستخدم", use_container_width=True):
            if new_username and new_password:
                if add_user(new_username, new_password, new_role, new_pharmacist_name):
                    st.success(f"✅ تم إضافة المستخدم {new_username}")
                    st.rerun()
                else:
                    st.error("❌ اسم المستخدم موجود مسبقاً")
            else:
                st.error("❌ الرجاء إدخال اسم المستخدم وكلمة المرور")
    
    # عرض المستخدمين
    st.markdown("### 📋 قائمة المستخدمين")
    users_df = get_all_users()
    
    if not users_df.empty:
        for idx, row in users_df.iterrows():
            with st.container():
                col1, col2, col3, col4, col5 = st.columns([1.5, 1.5, 2, 2, 1])
                
                with col1:
                    st.markdown(f"**👤 {row['username']}**")
                    st.caption(f"نوع: {row['role']}")
                
                with col2:
                    st.markdown(f"**اسم الصيدلي:** {row['pharmacist_name'] or '-'}")
                    st.caption(f"آخر دخول: {row['last_login'][:16] if row['last_login'] else 'لم يدخل'}")
                
                with col3:
                    st.markdown("**الصلاحيات:**")
                    can_dash = "✅" if row['can_view_dashboard'] else "❌"
                    can_bal = "✅" if row['can_view_balances'] else "❌"
                    can_mon = "✅" if row['can_view_monitoring'] else "❌"
                    can_users = "✅" if row['can_manage_users'] else "❌"
                    st.caption(f"لوحة التحكم: {can_dash} | تحديث الأرصدة: {can_bal}")
                    st.caption(f"مراقبة التعديلات: {can_mon} | إدارة المستخدمين: {can_users}")
                
                with col4:
                    if row['username'] != "admin":
                        new_pharm_name = st.text_input("اسم الصيدلي", value=row['pharmacist_name'] or "", key=f"name_{idx}")
                        perms = {
                            "can_view_dashboard": st.checkbox("لوحة التحكم", value=bool(row['can_view_dashboard']), key=f"dash_{idx}"),
                            "can_view_balances": st.checkbox("تحديث الأرصدة", value=bool(row['can_view_balances']), key=f"bal_{idx}"),
                            "can_view_monitoring": st.checkbox("مراقبة التعديلات", value=bool(row['can_view_monitoring']), key=f"mon_{idx}"),
                            "can_manage_users": st.checkbox("إدارة المستخدمين", value=bool(row['can_manage_users']), key=f"users_{idx}"),
                            "pharmacist_name": new_pharm_name
                        }
                        if st.button("💾 حفظ التعديلات", key=f"save_{idx}", use_container_width=True):
                            update_user_permissions(row['username'], perms)
                            st.success(f"✅ تم تحديث صلاحيات {row['username']}")
                            st.rerun()
                
                with col5:
                    if row['username'] != "admin":
                        if st.button("🗑️ حذف", key=f"delete_{idx}", use_container_width=True):
                            if delete_user(row['username']):
                                st.success(f"✅ تم حذف المستخدم {row['username']}")
                                st.rerun()
                            else:
                                st.error("لا يمكن حذف المستخدم admin")
                
                st.divider()
    else:
        st.info("لا توجد مستخدمين")