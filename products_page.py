import streamlit as st
import pandas as pd
import io
from datetime import datetime
from utils import (
    get_headers, safe_api_request, get_flat_price, update_product_status, 
    export_products_to_excel, upload_product_image_api, update_product_promotions_secure,
    get_branches_list, get_product_quantities_by_branch, generate_quantities_template, process_quantities_import
)

def render_products_page():
    st.markdown("<h2 style='color:#0f1c2e;'>📦 مركز إدارة المنتجات الذكي</h2>", unsafe_allow_html=True)
    
    headers = get_headers()
    if not headers: return

    # =========================================================================
    # ✅ 1. الإعدادات السريعة وإدارة الفروع
    # =========================================================================
    col_widget1, col_widget2 = st.columns(2)

    with col_widget1:
        with st.expander("⚙️ إعدادات ربط تطبيقات التوصيات وشاهدتها مؤخراً", expanded=False):
            st.markdown("#### 🛠️ إعدادات المنتجات المستعرضة مؤخراً")
            section_title = st.text_input("📝 عنوان القسم الفعال:", value="شاهدتها مؤخراً", key="app_recent_section_title")
            st.markdown("**🎯 تخصيص ظهور القسم في الصفحات:**")
            show_home = st.checkbox("الصفحة الرئيسية بالمتجر", value=False, key="app_show_home_recent")
            show_categories = st.checkbox("صفحة التصنيفات والأقسام", value=False, key="app_show_cat_recent")
            show_details = st.checkbox("صفحة تفاصيل وعرض المنتج", value=True, key="app_show_details_recent")
            products_limit = st.number_input("🔢 عدد المنتجات المعروضة:", min_value=1, max_value=32, value=6, key="app_recent_limit")
            
            st.markdown("#### 🛠️ نظام التوصية الذكي والحزم")
            global_enable = st.checkbox("✅ تفعيل التوصيات", value=True, key="app_reco_global_enable")
            buy_together = st.checkbox("🤝 تشترى معًا", value=True, key="app_reco_buy_together")
            prod_group = st.checkbox("📦 عرض المنتجات كحزمة", value=True, key="app_reco_prod_group")
            cart_btn_option = st.selectbox("🛒 عرض زر إضافة للسلة:", ["في صفحة السلة فقط", "في جميع الصفحات"], index=0, key="app_reco_cart_btn")
            
            if st.button("💾 حفظ وتثبيت إعدادات التطبيقات", type="primary", use_container_width=True):
                st.success("✅ تم حفظ إعدادات ربط التطبيقات بنجاح!")

    with col_widget2:
        # 🏢 الحاوية المسترجعة: إدارة كميات الفروع
        with st.expander("🏢 التحكم في كميات ومخزون الفروع", expanded=False):
            st.markdown("#### 📦 إدارة وتحديث كميات الفروع (Bulk Quantities)")
            
            cb1, cb2 = st.columns(2)
            with cb1:
                if st.button("👁️ عرض الفروع وكمياتها الحالية", use_container_width=True):
                    st.session_state["show_branches_data"] = True
            with cb2:
                template_q = generate_quantities_template()
                st.download_button("📥 تحميل نموذج استيراد الكميات", data=template_q, file_name="Salla_Quantities_Template.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
            
            uploaded_q_file = st.file_uploader("📂 رفع ملف Excel لتحديث الكميات للفروع:", type=['xlsx'], key="upload_quantities_file")
            if uploaded_q_file:
                if st.button("🚀 تحديث كميات الفروع", type="primary", use_container_width=True):
                    df_q = pd.read_excel(uploaded_q_file)
                    with st.spinner("جاري تحديث الكميات في سلة..."):
                        res_q = process_quantities_import(df_q)
                        for m in res_q["success"]: st.success(m)
                        for m in res_q["errors"]: st.error(m)
            
            # عرض بيانات الفروع إذا تم طلبها
            if st.session_state.get("show_branches_data", False):
                st.divider()
                with st.spinner("جاري جلب الفروع..."):
                    branches = get_branches_list()
                    if branches:
                        b_options = {b['name']: b['id'] for b in branches}
                        sel_branch_name = st.selectbox("اختر الفرع لعرض كمياته:", ["الكل"] + list(b_options.keys()))
                        b_id = b_options.get(sel_branch_name) if sel_branch_name != "الكل" else None
                        
                        quantities_data = get_product_quantities_by_branch(b_id)
                        if quantities_data:
                            st.info(f"📊 عدد السجلات المتوفرة: {len(quantities_data)}")
                            q_df = pd.DataFrame(quantities_data)
                            st.dataframe(q_df[['name', 'sku', 'quantity', 'unlimited_quantity']], use_container_width=True)
                        else:
                            st.warning("لا توجد كميات مسجلة لهذا الفرع.")
                    else:
                        st.warning("لا توجد فروع مسجلة في المتجر.")
                
                if st.button("إخفاء بيانات الفروع", use_container_width=True):
                    st.session_state["show_branches_data"] = False
                    st.rerun()

    st.divider()

    # ==========================================
    # ✅ 2. الفلاتر والبحث في المنتجات
    # ==========================================
    st.markdown("### 🔍 أدوات التصفية والبحث في المنتجات")
    
    with st.spinner("🔄 جاري تحميل المنتجات..."):
        prod_res = safe_api_request("GET", "https://api.salla.dev/admin/v2/products?per_page=100", headers)
        all_products = prod_res.get("data", []) if prod_res else []
    
    c_search, c_sort = st.columns([3, 1])
    with c_search:
        search_query = st.text_input("ابحث عن منتج (اسم، SKU، ID):", placeholder="أدخل اسم المنتج، أو الرقم التعريفي...")
    
    st.markdown("#### 🎯 فلاتر سريعة:")
    f_col1, f_col2, f_col3, f_col4, f_col5 = st.columns(5)
    with f_col1: filter_hidden = st.checkbox("المنتجات المخفية فقط", key="f_hidden")
    with f_col2: filter_no_img = st.checkbox("منتجات بدون صورة", key="f_no_img")
    with f_col3: filter_has_promo = st.checkbox("له عنوان ترويجي", key="f_promo")
    with f_col4: filter_discounted = st.checkbox("لها سعر مخفض", key="f_discount")
    with f_col5: filter_out_stock = st.checkbox("منتجات نفذت كميتها", key="f_out")

    available_end_dates = set()
    for p in all_products:
        end_d = p.get('sale_end') or (p.get('sale_price', {}).get('expired_at') if isinstance(p.get('sale_price'), dict) else None)
        if end_d: available_end_dates.add(end_d[:10])
        
    date_options = ["الكل"] + sorted(list(available_end_dates))
    selected_end_date = st.selectbox("📅 اختر تاريخ نهاية التخفيض للتصفية:", date_options, key="f_end_date_select")

    st.divider()

    # --- تطبيق الفلاتر ---
    filtered_products = []
    for p in all_products:
        p_id = str(p.get('id', ''))
        p_name = str(p.get('name', '')).lower()
        p_sku = str(p.get('sku', '')).lower()
        
        if search_query:
            sq = search_query.lower()
            if sq not in p_name and sq not in p_sku and sq != p_id: continue
                
        if filter_hidden and p.get('status') != 'hidden': continue
        if filter_no_img and p.get('thumbnail'): continue
        if filter_has_promo and not p.get('promotion_title'): continue
        if filter_out_stock and p.get('quantity', 0) > 0: continue
        
        has_disc = False
        pr = get_flat_price(p.get('price', 0))
        reg = get_flat_price(p.get('regular_price', 0))
        sl = get_flat_price(p.get('sale_price', 0))
        if sl > 0 and sl < (reg if reg > 0 else pr): has_disc = True
        elif reg > 0 and pr < reg: has_disc = True
            
        if filter_discounted and not has_disc: continue
        
        if selected_end_date != "الكل":
            end_d = p.get('sale_end') or (p.get('sale_price', {}).get('expired_at') if isinstance(p.get('sale_price'), dict) else None)
            if not end_d or not end_d.startswith(selected_end_date): continue
                
        filtered_products.append(p)

    st.markdown(f"**📊 عدد المنتجات المطابقة:** {len(filtered_products)}")

    if filtered_products:
        ex_data = export_products_to_excel(filtered_products)
        st.download_button(
            label="📥 تحميل المنتجات المفلترة الحالية (Excel)",
            data=ex_data,
            file_name=f"Filtered_Products_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            key="direct_export_filtered_btn",
            use_container_width=True
        )

    # ==========================================
    # ✅ 3. عرض المنتجات وبطاقاتها
    # ==========================================
    for idx, p in enumerate(filtered_products):
        p_id = p.get('id', 'N/A')
        p_name = p.get('name', 'منتج بدون اسم')
        p_sku = p.get('sku', 'لا يوجد')
        status = p.get('status', 'sale')
        p_url = p.get('url', 'https://salla.sa')
        p_image = p.get('thumbnail')
        
        promo = p.get('promotion', {})
        p_promotion = p.get('promotion_title') or (promo.get('title') if isinstance(promo, dict) else '') or "لا يوجد عنوان ترويجي"
        p_sub_title = (promo.get('sub_title') if isinstance(promo, dict) else '') or "لا يوجد عنوان فرعي"
        
        price_val = get_flat_price(p.get('price', 0))
        regular_val = get_flat_price(p.get('regular_price', 0))
        sale_val = get_flat_price(p.get('sale_price', 0))

        base_price = regular_val if regular_val > 0 else price_val
        if sale_val > 0 and sale_val < base_price:
            display_sale_price = sale_val; has_discount = True
        elif price_val < regular_val and price_val > 0:
            display_sale_price = price_val; has_discount = True
        else:
            display_sale_price = base_price; has_discount = False

        discount_percent = int(((base_price - display_sale_price) / base_price) * 100) if has_discount and base_price > 0 else 0
        sale_start_date = p.get('sale_start') or (p.get('sale_price', {}).get('start_at') if isinstance(p.get('sale_price'), dict) else None) or "غير محدد"
        sale_end_date = p.get('sale_end') or (p.get('sale_price', {}).get('expired_at') if isinstance(p.get('sale_price'), dict) else None) or "غير محدد"
        
        disp_status = "🟢 معروض بالمتجر" if status == "sale" else "🔴 منتج مخفي"
        tax_status_badge = "‎🔥 خاضع للضريبة" if p.get('with_tax', True) else "⚪ معفى من الضريبة"
        
        # ✅ شارة الضرائب المسترجعة والمدمجة بذكاء
        st.markdown(f"""
            <div style="background: linear-gradient(135deg, #243b55 0%, #141e30 100%); 
                        padding: 14px 20px; border-radius: 12px 12px 0px 0px; 
                        margin-top: 25px; display: flex; justify-content: space-between; align-items: center; 
                        border-bottom: 3px solid #e67e22;">
                <span style="color: #ffffff; font-weight: bold; font-size: 15px;">📦 {p_name}</span>
                <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                    <span style="background: rgba(255,255,255,0.2); color: #fff; padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight:600;">{disp_status}</span>
                    <span style="background: rgba(0, 235, 207, 0.2); color: #00EBCF; padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight:600;">{tax_status_badge}</span>
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        with st.container():
            st.markdown("""<div style="background-color: #fafbfc; padding: 20px; border-radius: 0px 0px 12px 12px; border: 1px solid #e1e8ed; border-top: none; box-shadow: 0 4px 10px rgba(0,0,0,0.03); margin-bottom: 25px;">""", unsafe_allow_html=True)
            
            c_img, c_info, c_pricing, c_action = st.columns([1, 2.5, 3, 2])
            
            with c_img:
                if p_image:
                    st.image(p_image, use_container_width=True)
                else:
                    st.markdown("<div style='text-align:center; padding:30px; background:#eee; border-radius:8px;'>🚫 بدون صورة</div>", unsafe_allow_html=True)
                
                with st.popover("🖼️ إرفاق صورة"):
                    uploaded_img = st.file_uploader("اختر صورة للمنتج:", type=['png', 'jpg', 'jpeg'], key=f"img_up_{p_id}_{idx}")
                    if uploaded_img is not None:
                        if st.button("🚀 رفع الصورة للمنتج", key=f"btn_up_{p_id}_{idx}", type="primary"):
                            with st.spinner("جاري الرفع..."):
                                if upload_product_image_api(p_id, uploaded_img.getvalue(), uploaded_img.name):
                                    st.success("✅ تم رفع الصورة بنجاح!")
                                    st.rerun()
            
            with c_info:
                st.markdown(f"🆔 **المعرف:** `{p_id}` | 🔢 **SKU:** `{p_sku}`")
                st.markdown(f"📢 **عنوان ترويجي:** <span style='color:#e67e22; font-weight:bold;'>{p_promotion}</span>", unsafe_allow_html=True)
                st.markdown(f"🏷️ **عنوان فرعي:** `{p_sub_title}`")
                st.markdown(f"🔗 [🌐 معاينة المنتج]({p_url})")
                st.markdown(f"📦 **المخزون:** `{p.get('quantity', 0)}` | 📈 **المبيعات:** `{p.get('sold_quantity', 0)}`")
                # ✅ زر عرض ارصدة الفروع
                if st.button("🏪 عرض ارصدة الفروع", key=f"branches_stock_{p_id}_{idx}"):
                    st.session_state[f"show_branches_{p_id}"] = True
                    
                if st.session_state.get(f"show_branches_{p_id}", False):
                    with st.container():
                        st.markdown("---")
                        st.markdown("#### 🏪 ارصدة المنتج بالفروع")
                            
                        branches_res = safe_api_request(
                            "GET",
                            f"https://api.salla.dev/admin/v2/products/{p_id}/branches",
                            headers
                        )
                            
                        if branches_res and branches_res.get("data"):
                            branches = branches_res["data"]
                            for branch in branches:
                                st.markdown(f"""
                                    <div style="display: flex; justify-content: space-between; 
                                                padding: 4px 10px; background: #f8f9fa; 
                                                border-radius: 6px; margin: 2px 0;
                                                border-right: 3px solid #00b4d8;">
                                        <span><b>{branch.get('name', 'فرع غير معروف')}</b></span>
                                        <span>📦 {branch.get('quantity', 0)} حبة</span>
                                    </div>
                                """, unsafe_allow_html=True)
                        else:
                            st.info("ℹ️ لا توجد فروع متاحة أو المنتج غير مرتبط بفروع")
                            
                        if st.button("❌ إخفاء الارصدة", key=f"hide_branches_{p_id}_{idx}"):
                            st.session_state[f"show_branches_{p_id}"] = False
                            st.rerun()
            
            with c_pricing:
                if has_discount:
                    st.markdown(f"""
                    <div style="background:#fff3cd; padding:10px; border-radius:8px; border-right:5px solid #ffc107;">
                        <span style="text-decoration: line-through; color: #7f8c8d; font-size:12px;">أصلي: {base_price:,.2f} SAR</span><br>
                        <b style="color: #c0392b; font-size:15px;">مخفض: {display_sale_price:,.2f} SAR</b>
                        <span style="background:#c0392b; color:#fff; padding:2px 5px; border-radius:4px; font-size:10px; margin-right:5px;">وفرت: {discount_percent}%</span>
                    </div>
                    """, unsafe_allow_html=True)
                    st.markdown(f"📅 **بداية التخفيض:** `{sale_start_date}`")
                    st.markdown(f"📅 نهاية التخفيض: `{sale_end_date}`")                    
                else:
                    st.markdown(f"""<div style="background:#e2e8f0; padding:10px; border-radius:8px; border-right:5px solid #4a5568;"><b style="color:#2d3748; font-size:14px;">سعر ثابت: {base_price:,.2f} SAR</b></div>""", unsafe_allow_html=True)
                    
            with c_action:
                st.markdown("<br>", unsafe_allow_html=True)
                target_st = "hidden" if status == "sale" else "sale"
                btn_lbl = "👁️ إخفاء المنتج من المتجر" if status == "sale" else "👁️ إظهار المنتج بالمتجر"
                if st.button(btn_lbl, key=f"sh_{p_id}_{idx}", type="secondary" if status == "sale" else "primary", use_container_width=True):
                    with st.spinner("مزامنة..."):
                        if update_product_status(p_id, target_st):
                            st.success("تم التحديث!")
                            st.rerun()
                            
                # التعديل المحمي للأسعار والعناوين
                with st.popover("✏️ تعديل العناوين"):
                    new_promo = st.text_input("العنوان الترويجي:", value=(p_promotion if p_promotion != "لا يوجد عنوان ترويجي" else ""), key=f"promo_in_{p_id}_{idx}")
                    new_sub = st.text_input("العنوان الفرعي:", value=(p_sub_title if p_sub_title != "لا يوجد عنوان فرعي" else ""), key=f"sub_in_{p_id}_{idx}")
                    
                    if st.button("💾 حفظ التعديلات", key=f"save_promo_{p_id}_{idx}", type="primary", use_container_width=True):
                        with st.spinner("جاري الحفظ الآمن..."):
             safe_api_request(
                                "PUT",
                                f"https://api.salla.dev/admin/v2/products/{p_id}",
                                headers,
                                json={"promotion_title": new_promo, new_sub}
                              )
                            if update_product_promotions_secure(p_id, new_promo, new_sub, headers):
                                st.success("✅ تم تحديث العناوين بنجاح!")
                                st.rerun()

            st.markdown("</div>", unsafe_allow_html=True)
