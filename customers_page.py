import streamlit as st
from utils import (
    get_headers, safe_float, get_customers_list, create_customer, update_customer_api,
    delete_customer_api, get_customer_groups_list, create_customer_group,
    update_customer_group_api, delete_customer_group_api,
    export_customers_to_excel, export_customer_groups_to_excel
)

def render_customers_page():
    st.markdown("""
    <div style="background: linear-gradient(135deg, #0F1C2E 0%, #00EBCF 100%); padding: 15px 25px; border-radius: 12px; color: white; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
        <h2 style="color: white; margin: 0;">👥 مركز إدارة العملاء والمجموعات</h2>
    </div>
    """, unsafe_allow_html=True)
    
    headers = get_headers()
    if not headers: return

    tab_customers, tab_groups = st.tabs(["👤 إدارة ملفات العملاء", "🏷️ المجموعات والتصنيفات"])

    # ==========================================
    # 👤 علامة التبويب الأولى: إدارة العملاء
    # ==========================================
    with tab_customers:
        st.markdown("### 👤 التحكم في بيانات العملاء والمشتريات")
        
        # حاوية إنشاء عميل جديد
        with st.expander("➕ إضافة عميل جديد إلى المنظومة", expanded=False):
            cc1, cc2 = st.columns(2)
            with cc1:
                c_first = st.text_input("الاسم الأول للعميل:", key="c_first_new")
                c_last = st.text_input("اسم العائلة:", key="c_last_new")
                c_email = st.text_input("البريد الإلكتروني:", key="c_email_new")
                c_gender = st.selectbox("الجنس:", ["male", "female"], format_func=lambda x: "ذكر" if x=="male" else "أنثى", key="c_gender_new")
            with cc2:
                c_mobile = st.text_input("رقم الجوال (بدون صفر أو رمز الدولة):", key="c_mob_new")
                c_code = st.text_input("رمز الدولة للجوال:", value="+966", key="c_code_new")
                c_city = st.text_input("مدينة العميل الحالية:", value="Riyadh", key="c_city_new")
                c_loc = st.text_input("المنطقة / تفاصيل العنوان:", placeholder="شارع، رقم المبنى", key="c_loc_new")
            
            if st.button("🚀 تدوين ونشر العميل الجديد للمتجر", type="primary", use_container_width=True):
                payload = {
                    "first_name": c_first, "last_name": c_last, "email": c_email, "gender": c_gender,
                    "mobile": c_mobile, "mobile_code_country": c_code, "city": c_city, "location": c_loc
                }
                if create_customer(payload):
                    st.success("✅ تم إضافة العميل الجديد للمتجر بنجاح!")
                    st.rerun()

        st.divider()
        
        # شريط البحث والجلب
        search_kw = st.text_input("🔍 ابحث عن عميل برقم الجوال، البريد الإلكتروني أو الاسم:")
        with st.spinner("جاري جلب بيانات العملاء..."):
            res_cust = get_customers_list(keyword=search_kw)
            
        if res_cust and res_cust.get("data"):
            customers = res_cust["data"]
            
            # زر تصدير العملاء المنسق باحترافية
            st.download_button(
                label="📥 تصدير قائمة العملاء الحالية إلى Excel",
                data=export_customers_to_excel(customers),
                file_name="Balsem_Customers_Report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="export_customers_btn_excel"
            )
            st.markdown("<br>", unsafe_allow_html=True)

            for idx, cust in enumerate(customers):
                cust_id = cust.get('id', 'N/A')
                full_name = f"{cust.get('first_name', '')} {cust.get('last_name', '')}"
                
                stats = cust.get('stats', {})
                orders_count = stats.get('orders_count', 0) if isinstance(stats, dict) else 0
                orders_amount = safe_float(stats.get('orders_amount', 0.0)) if isinstance(stats, dict) else 0.0
                
                # ترويسة الحاوية الفاخرة للعميل
                st.markdown(f"""
                    <div style="background: linear-gradient(135deg, #0f1c2e 0%, #1a365d 100%); 
                                padding: 12px 20px; border-radius: 12px 12px 0px 0px; 
                                margin-top: 20px; display: flex; justify-content: space-between; align-items: center; border-bottom: 3px solid #00b4d8;">
                        <span style="color: #ffffff; font-weight: bold; font-size: 15px;">👤 {full_name} (ID: {cust_id})</span>
                        <span style="background: rgba(255,255,255,0.2); color: #fff; padding: 3px 10px; border-radius: 15px; font-size: 11px;">📊 إجمالي المشتريات: {orders_amount:,.2f} SAR</span>
                    </div>
                """, unsafe_allow_html=True)
                
                with st.container():
                    st.markdown("""
                        <div style="background-color: #ffffff; padding: 20px; border-radius: 0px 0px 12px 12px; 
                                    border: 1px solid #e8edf2; border-top: none; box-shadow: 0 4px 12px rgba(0,0,0,0.05); margin-bottom: 20px;">
                    """, unsafe_allow_html=True)
                    
                    cx1, cx2, cx3 = st.columns([3, 3, 2])
                    with cx1:
                        st.markdown(f"📱 **رقم اتصال الجوال:** `+{cust.get('mobile_code', '')}{cust.get('mobile', '')}`")
                        st.markdown(f"✉️ **البريد الإلكتروني:** `{cust.get('email', 'لا يوجد')}`")
                        st.markdown(f"🚻 **الجنس:** `{'ذكر' if cust.get('gender') == 'male' else 'أنثى'}`")
                    with cx2:
                        st.markdown(f"📍 **الدولة والمدينة:** `{cust.get('country', 'السعودية')} - {cust.get('city', 'غير محددة')}`")
                        st.markdown(f"🗺️ **المنطقة وتفاصيل العنوان المحدد:** `{cust.get('location', 'لا يوجد عنوان مسجل')}`")
                        st.markdown(f"📦 **عدد الطلبات المنجزة:** `{orders_count} طلب`")
                    with cx3:
                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.button("🗑️ حذف الحساب", key=f"del_c_{cust_id}_{idx}", use_container_width=True):
                            if delete_customer_api(cust_id):
                                st.success(" تم حذف العميل بنجاح!")
                                st.rerun()
                                
                    # ✅ تصحيح الـ NameError بالاعتماد الكامل على كائن cust بدلاً من p المتداخل سابقاً
                    with st.expander("✏️ مراجعة وتحديث ملف هذا العميل", expanded=False):
                        ec1, ec2 = st.columns(2)
                        with ec1:
                            ed_f_name = st.text_input("الاسم الأول:", value=cust.get('first_name', ''), key=f"ed_fn_{cust_id}_{idx}")
                            ed_l_name = st.text_input("الاسم الأخير:", value=cust.get('last_name', ''), key=f"ed_ln_{cust_id}_{idx}")
                        with ec2:
                            ed_mail = st.text_input("تحديث الإيميل:", value=cust.get('email', ''), key=f"ed_em_{cust_id}_{idx}")
                            ed_loc = st.text_input("تحديث المنطقة / العنوان الحركي:", value=str(cust.get('location', '')), key=f"ed_lc_{cust_id}_{idx}")
                        
                        if st.button("💾 حفظ تحديثات ملف العميل", key=f"btn_sv_c_{cust_id}_{idx}", type="primary", use_container_width=True):
                            payload_update = {
                                "first_name": ed_f_name, 
                                "last_name": ed_l_name, 
                                "email": ed_mail, 
                                "location": ed_loc
                            }
                            if update_customer_api(cust_id, payload_update):
                                st.success("✅ تم تحديث بيانات العميل بنجاح!")
                                st.rerun()

                    st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.warning("⚠️ لا يوجد عملاء يطابقون خيارات البحث الحالية.")

    # ==========================================
    # 🏷️ علامة التبويب الثانية: إدارة مجموعات العملاء
    # ==========================================
    with tab_groups:
        st.markdown("### 🏷️ تجميع وتصنيف مجموعات العملاء المتقدمة")
        
        # حاوية إنشاء مجموعة عملاء جديدة
        with st.expander("➕ إنشاء مجموعة عملاء مؤتمتة جديدة", expanded=False):
            g_name = st.text_input("اسم وتسمية المجموعة (مثل: عملاء VIP):", key="g_name_new")
            g_cond_type = st.selectbox("شروط التصنيف التلقائي بناءً على:", ["total_sales", "total_orders", "store_rating", "doesnt_have_orders"], format_func=lambda x: "إجمالي المبيعات" if x=="total_sales" else "عدد الطلبات" if x=="total_orders" else "تقييم المتجر" if x=="store_rating" else "عملاء بلا أي طلبات")
            g_symbol = st.selectbox("العامل الرياضي المطبق للشرط:", [">", "<", "between"])
            g_val = st.number_input("قيمة الشرط المستهدفة:", min_value=0.0, value=100.0)
            
            if st.button("🚀 إنشاء مصفوفة المجموعة الجديدة", type="primary", use_container_width=True):
                group_payload = {
                    "name": g_name,
                    "conditions": [{"type": g_cond_type, "symbol": g_symbol, "value": g_val}],
                    "features": {"payment_method": ["credit_card", "mada"], "shipping": ["all"]}
                }
                if create_customer_group(group_payload):
                    st.success("✅ تم إنشاء تصنيف المجموعة التلقائية بنجاح!")
                    st.rerun()

        st.divider()
        
        with st.spinner("جاري جلب مجموعات الجرد الحالية..."):
            res_groups = get_customer_groups_list()
            
        if res_groups and res_groups.get("data"):
            groups = res_groups["data"]
            
            # زر تصدير مجموعات العملاء المنسق باحترافية
            st.download_button(
                label="📥 تصدير مجموعات العملاء الحالية إلى Excel",
                data=export_customer_groups_to_excel(groups),
                file_name="Balsem_Customer_Groups_Report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="export_groups_btn_excel"
            )
            st.markdown("<br>", unsafe_allow_html=True)

            for g_idx, group in enumerate(groups):
                group_id = group.get('id', 'N/A')
                group_name = group.get('name', 'تصنيف غير مسمى')
                
                st.markdown(f"""
                    <div style="background: linear-gradient(135deg, #1f2d3d 0%, #2c3e50 100%); 
                                padding: 12px 20px; border-radius: 12px 12px 0px 0px; 
                                margin-top: 20px; display: flex; justify-content: space-between; align-items: center; border-bottom: 3px solid #e67e22;">
                        <span style="color: #ffffff; font-weight: bold; font-size: 15px;">🏷️ مجموعة: {group_name} (معرف المجموعة ID: {group_id})</span>
                    </div>
                """, unsafe_allow_html=True)
                
                with st.container():
                    st.markdown("""
                        <div style="background-color: #fafbfc; padding: 20px; border-radius: 0px 0px 12px 12px; 
                                    border: 1px solid #e1e8ed; border-top: none; box-shadow: 0 4px 10px rgba(0,0,0,0.03); margin-bottom: 20px;">
                    """, unsafe_allow_html=True)
                    
                    g_col1, g_col2 = st.columns([5, 3])
                    with g_col1:
                        st.markdown(f"📌 **مسمى الفئة المستهدفة:** `{group_name}`")
                        st.markdown(f"🆔 **المعرف الرقمي للمجموعة الموحد:** `{group_id}`")
                    with g_col2:
                        if st.button("🗑️ حذف المجموعة نهائياً", key=f"del_g_{group_id}_{g_idx}", use_container_width=True):
                            if delete_customer_group_api(group_id):
                                st.success(" تم حذف مجموعة العملاء وتفكيك الأصناف المربوطة بها!")
                                st.rerun()
                                
                    with st.expander("✏️ مراجعة وتحديث مسمى هذه المجموعة", expanded=False):
                        ed_g_name = st.text_input("تعديل اسم المجموعة الحالية:", value=group_name, key=f"ed_gn_in_{group_id}_{g_idx}")
                        if st.button("💾 حفظ تحديثات اسم المجموعة", key=f"btn_sv_g_{group_id}_{g_idx}", type="primary", use_container_width=True):
                            if update_customer_group_api(group_id, {"name": ed_g_name}):
                                st.success("✅ تم تحديث مسمى المجموعة بنجاح!")
                                st.rerun()

                    st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.info("ℹ️ لا يوجد أي مجموعات عملاء مخصصة منشأة حالياً في حسابك.")
