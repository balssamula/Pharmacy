import streamlit as st
import pandas as pd
import sqlite3
from utils.database import DB_PATH, get_all_users, add_user, delete_user, update_user_permissions

def fix_permissions_table_columns():
    """حقن صامت لترميم جدول الصلاحيات وإضافة الأعمدة الخاصة بالصفحات الجديدة منعاً للانهيار"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    new_columns = [
        "can_manage_offers",
        "can_view_products",
        "can_view_analytics"
    ]
    for col in new_columns:
        try:
            # إضافة الأعمدة الجديدة كـ INTEGER (0 أو 1)
            cur.execute(f"ALTER TABLE user_permissions ADD COLUMN {col} INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # العمود موجود مسبقاً، تخطى بأمان
    conn.commit()
    conn.close()

# تشغيل دالة الترميم التلقائي للأعمدة فور استدعاء الصفحة
fix_permissions_table_columns()

def show():
    st.markdown(
        """
        <div class="hero">
            <h1>👥 إدارة المستخدمين والصلاحيات المتقدمة</h1>
            <p>إضافة وتعديل حسابات النظام وتعيين صلاحيات الوصول الصارمة لكل صفحة بشكل مستقل</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    # دالة مساعدة لتحويل القيم إلى قيم منطقية Boolean بأمان
    def safe_bool(val):
        return str(val).strip() in ['1', 'True', 'true', 'T', 't']

    # 1️⃣ قسم إضافة مستخدم جديد
    with st.expander("➕ إضافة مستخدم جديد للنظام", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            new_username = st.text_input("👤 اسم المستخدم الجديد", placeholder="مثال: pharmacy_branch_1")
            new_password = st.text_input("🔑 كلمة المرور", type="password", placeholder="أدخل كلمة مرور قوية...")
        with col2:
            new_role = st.selectbox("⚙️ دور الحساب (Role)", ["pharmacy", "manager", "admin"])
            new_pharmacist_name = st.text_input("👤 اسم الشخص / الصيدلي المسؤول")
        
        if st.button("➕ اعتماد وإضافة المستخدم الجديد", use_container_width=True):
            if new_username and new_password:
                if add_user(new_username, new_password, new_role, new_pharmacist_name):
                    st.success(f"🎉 تم إضافة المستخدم [{new_username}] بنجاح وإصدار ملف صلاحياته.")
                    st.rerun()
                else:
                    st.error("❌ فشل الإدخال. اسم المستخدم مسجل مسبقاً بقاعدة البيانات.")
            else:
                st.warning("⚠️ يرجى ملء حقول اسم المستخدم وكلمة المرور أولاً.")
                
    st.markdown("### 📋 قائمة الحسابات النشطة والتحكم في صلاحيات الصفحات")
    
    users_df = get_all_users()
    
    if not users_df.empty:
        for idx, row in users_df.iterrows():
            # تمييز الحسابات الرئيسية بلون مختلف
            is_master = row['username'] in ["admin", "manager"]
            bg_color = "#f0f7f7" if is_master else "#ffffff"
            
            with st.container():
                st.markdown(f"""
                <div style="background:{bg_color}; border-radius:12px; padding:1rem; margin-bottom:0.5rem; border:1px solid #e2e8f0;">
                    <strong>👤 اسم المستخدم: {row['username']}</strong> | 🔑 الدور: <span style="color:#1f7a8c; font-weight:bold;">{str(row['role']).upper()}</span>
                </div>
                """, unsafe_allow_html=True)
                
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    if row['username'] != "admin":  # حساب الـ admin يملك كل شيء دائماً ومحمي من التعديل
                        st.markdown("##### 🔓 حدد الصفحات المسموح لهذا الحساب بفتحها:")
                        
                        cc1, cc2, cc3 = st.columns(3)
                        with cc1:
                            c_dash = st.checkbox("📊 التسويات والمطابقات الممالية", value=safe_bool(row.get('can_view_dashboard', 0)), key=f"dash_{idx}")
                            c_manage_users = st.checkbox("👥 إدارة صلاحيات المستخدمين", value=safe_bool(row.get('can_manage_users', 0)), key=f"mgr_{idx}")
                        with cc2:
                            c_offers = st.checkbox("🎁 مركز العروض الخاصة (سلة)", value=safe_bool(row.get('can_manage_offers', 0)), key=f"off_{idx}")
                            c_balances = st.checkbox("💰 تحديث ورفع الأرصدة", value=safe_bool(row.get('can_view_balances', 0)), key=f"bal_{idx}")
                        with cc3:
                            c_products = st.checkbox("📦 تفصيلي وجرد المنتجات", value=safe_bool(row.get('can_view_products', 0)), key=f"prod_{idx}")
                            c_analytics = st.checkbox("📈 تحليل مبيعات الشهور", value=safe_bool(row.get('can_view_analytics', 0)), key=f"anl_{idx}")
                            c_monitoring = st.checkbox("🖥️ شاشة المراقبة والنظام", value=safe_bool(row.get('can_view_monitoring', 0)), key=f"mon_{idx}")
                    else:
                        st.info("👑 هذا هو حساب المطور الرئيسي (Admin) - يمتلك صلاحيات مطلقة لكافة الصفحات بشكل تلقائي.")
                
                with col2:
                    if row['username'] != "admin":
                        if st.button("💾 حفظ الصلاحيات", key=f"save_{idx}", use_container_width=True):
                            # تجميع مصفوفة الصلاحيات الجديدة المحدثة المتوافقة مع app.py المطور
                            perms = {
                                "can_view_dashboard": 1 if c_dash else 0,
                                "can_manage_offers": 1 if c_offers else 0,
                                "can_view_products": 1 if c_products else 0,
                                "can_view_analytics": 1 if c_analytics else 0,
                                "can_manage_users": 1 if c_manage_users else 0,
                                "can_view_balances": 1 if c_balances else 0,
                                "can_view_monitoring": 1 if c_monitoring else 0,
                                "pharmacist_name": row.get('pharmacist_name', '') or ""
                            }
                            update_user_permissions(row['username'], perms)
                            st.toast(f"✅ تم تحديث وإغلاق ملف صلاحيات [{row['username']}] بنجاح!", icon="💾")
                            st.rerun()
                            
                        if row['username'] != "manager":
                            if st.button("🗑️ حذف الحساب", key=f"del_{idx}", use_container_width=True):
                                if delete_user(row['username']):
                                    st.success(f"🗑️ تم إقصاء وحذف حساب {row['username']} من النظام.")
                                    st.rerun()
                st.divider()
    else:
        st.info("📭 لا توجد حسابات مسجلة في قاعدة البيانات حالياً.")
