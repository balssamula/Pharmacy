import streamlit as st
import pandas as pd
from utils.database import get_all_users, add_user, delete_user, update_user_permissions, update_user, update_username

def show():
    st.markdown(
        """
        <div class="hero">
            <h1>👥 إدارة المستخدمين والصلاحيات</h1>
            <p>إضافة وتعديل وحذف المستخدمين وتحديد صلاحياتهم وتفعيل/تعطيل الحسابات</p>
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
            new_role = st.selectbox("نوع المستخدم", ["pharmacy", "manager", "admin"])
            new_pharmacist_name = st.text_input("اسم الشخص (للفروع فقط)")
        
        if st.button("➕ إضافة مستخدم", use_container_width=True):
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
                col1, col2, col3, col4, col5 = st.columns([1.2, 1.5, 2.5, 1.5, 1])
                
                with col1:
                    role_icon = "👑" if row['role'] == 'admin' else "📋" if row['role'] == 'manager' else "💊"
                    active_status = "🟢 نشط" if row['is_active'] else "🔴 غير نشط"
                    st.markdown(f"**{role_icon} {row['username']}**")
                    st.caption(f"نوع: {row['role']}")
                    st.caption(f"الحالة: {active_status}")
                
                with col2:
                    st.markdown(f"**الاسم:** {row['pharmacist_name'] or '-'}")
                    st.caption(f"آخر دخول: {row['last_login'][:16] if row['last_login'] else 'لم يدخل'}")
                
                with col3:
                    if row['username'] not in ["admin", "manager"]:
                        # حقل تعديل اسم المستخدم
                        new_username = st.text_input("اسم المستخدم الجديد", value=row['username'], key=f"uname_{idx}")
                        
                        # حقل تعديل الاسم
                        new_pharm_name = st.text_input("الاسم", value=row['pharmacist_name'] or "", key=f"name_{idx}")
                        
                        # حقل تغيير كلمة المرور
                        new_password = st.text_input("كلمة مرور جديدة (اتركه فارغاً للإبقاء)", type="password", key=f"pass_{idx}")
                        
                        # حقل تغيير الدور
                        new_role = st.selectbox("الدور", ["pharmacy", "manager", "admin"], 
                                                index=["pharmacy", "manager", "admin"].index(row['role']) if row['role'] in ["pharmacy", "manager", "admin"] else 0,
                                                key=f"role_{idx}")
                        
                        # تفعيل/تعطيل المستخدم
                        is_active = st.checkbox("مفعل", value=bool(row['is_active']), key=f"active_{idx}")
                        
                        # الصلاحيات
                        can_dash = st.checkbox("📊 لوحة التحكم", value=bool(row['can_view_dashboard']), key=f"dash_{idx}")
                        can_bal = st.checkbox("🔄 تحديث الأرصدة", value=bool(row['can_view_balances']), key=f"bal_{idx}")
                        can_mon = st.checkbox("👥 مراقبة التعديلات", value=bool(row['can_view_monitoring']), key=f"mon_{idx}")
                        can_pharm = st.checkbox("🏥 إجراءات الصيدليات", value=bool(row['can_view_pharmacy_actions']), key=f"pharm_{idx}")
                        can_users = st.checkbox("👥 إدارة المستخدمين", value=bool(row['can_manage_users']), key=f"users_{idx}")
                        
                        if st.button("💾 حفظ التعديلات", key=f"save_{idx}"):
                            # تحديث اسم المستخدم إذا تغير
                            if new_username != row['username']:
                                if update_username(row['username'], new_username, new_password if new_password else None):
                                    st.success(f"✅ تم تحديث اسم المستخدم إلى {new_username}")
                                    st.rerun()
                                else:
                                    st.error("❌ اسم المستخدم موجود مسبقاً")
                            else:
                                # تحديث بيانات المستخدم الأساسية
                                if new_password:
                                    update_user(row['username'], password=new_password, 
                                               pharmacist_name=new_pharm_name, role=new_role, is_active=is_active)
                                else:
                                    update_user(row['username'], pharmacist_name=new_pharm_name, 
                                               role=new_role, is_active=is_active)
                                
                                # تحديث الصلاحيات
                                perms = {
                                    "can_view_dashboard": can_dash,
                                    "can_view_balances": can_bal,
                                    "can_view_monitoring": can_mon,
                                    "can_view_pharmacy_actions": can_pharm,
                                    "can_manage_users": can_users,
                                    "pharmacist_name": new_pharm_name
                                }
                                update_user_permissions(row['username'], perms)
                                st.success(f"✅ تم تحديث بيانات {row['username']}")
                                st.rerun()
                    elif row['username'] == "manager":
                        st.info("🔧 مدير عام - يمكن تعديل صلاحياته")
                        can_dash = st.checkbox("📊 لوحة التحكم", value=bool(row['can_view_dashboard']), key=f"dash_mgr")
                        can_bal = st.checkbox("🔄 تحديث الأرصدة", value=bool(row['can_view_balances']), key=f"bal_mgr")
                        can_mon = st.checkbox("👥 مراقبة التعديلات", value=bool(row['can_view_monitoring']), key=f"mon_mgr")
                        can_pharm = st.checkbox("🏥 إجراءات الصيدليات", value=bool(row['can_view_pharmacy_actions']), key=f"pharm_mgr")
                        
                        if st.button("💾 حفظ صلاحيات المدير العام", key=f"save_manager"):
                            perms = {
                                "can_view_dashboard": can_dash,
                                "can_view_balances": can_bal,
                                "can_view_monitoring": can_mon,
                                "can_view_pharmacy_actions": can_pharm,
                                "can_manage_users": False,
                                "pharmacist_name": row['pharmacist_name'] or ""
                            }
                            update_user_permissions(row['username'], perms)
                            st.success("✅ تم تحديث صلاحيات المدير العام")
                            st.rerun()
                    else:
                        st.info("👑 المدير العام - جميع الصلاحيات")
                
                with col4:
                    if row['username'] not in ["admin", "manager"]:
                        if st.button("🗑️ حذف", key=f"delete_{idx}"):
                            if delete_user(row['username']):
                                st.success(f"✅ تم حذف المستخدم {row['username']}")
                                st.rerun()
                
                st.divider()
    else:
        st.info("لا توجد مستخدمين")
