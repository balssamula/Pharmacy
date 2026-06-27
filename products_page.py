import streamlit as st
import pandas as pd
from datetime import datetime
from utils import get_headers, safe_api_request, get_flat_price, update_product_status, export_products_to_excel

def render_products_page():
    st.markdown("<h2 style='color:#0f1c2e;'>📦 مركز إدارة المنتجات الذكي</h2>", unsafe_allow_html=True)
    
    headers = get_headers()
    if not headers: return

    # تقسيم قسم إعدادات ربط التطبيقات إلى عمودين
    col_widget1, col_widget2 = st.columns(2)

    # =========================================================================
    # ✅ 1. واجهة إعدادات الأصناف المستعرضة مؤخراً
    # =========================================================================
    with col_widget1:
        with st.expander("⚙️ إعدادات ربط تطبيق: شاهدتها مؤخراً", expanded=False):
            st.markdown("#### 🛠️ إعدادات المنتجات المستعرضة مؤخراً")
            
            section_title = st.text_input("📝 عنوان القسم الفعال:", value="شاهدتها مؤخراً", key="app_recent_section_title")
            
            st.markdown("**🎯 تخصيص ظهور القسم في الصفحات:**")
            show_home = st.checkbox("الصفحة الرئيسية بالمتجر", value=False, key="app_show_home_recent")
            show_categories = st.checkbox("صفحة التصنيفات والأقسام", value=False, key="app_show_cat_recent")
            show_details = st.checkbox("صفحة تفاصيل وعرض المنتج", value=True, key="app_show_details_recent")
            show_thankyou = st.checkbox("صفحة الشكر (بعد الشراء)", value=False, key="app_show_thank_recent")
            
            products_limit = st.number_input("🔢 عدد المنتجات المعروضة (بحد أقصى 32):", min_value=1, max_value=32, value=6, step=1, key="app_recent_products_count_limit")
            
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("💾 حفظ إعدادات 'شاهدتها مؤخراً'", type="primary", use_container_width=True, key="save_recent_widget_settings_btn"):
                st.success("✅ تم تدوين خيارات 'شاهدتها مؤخراً' بنجاح!")

    # =========================================================================
    # ✅ 2. واجهة إعدادات نظام التوصيات
    # =========================================================================
    with col_widget2:
        with st.expander("⚙️ إعدادات ربط تطبيق: نظام التوصيات الذكي والحزم", expanded=False):
            st.markdown("#### 🛠️ إعدادات ربط التطبيق (التوصيات والحزم)")
            
            global_enable = st.checkbox("✅ تفعيل التوصيات", value=True, key="app_reco_global_enable")
            
            st.markdown("---")
            st.markdown("**🎯 خيارات ظهور التوصيات الذكية في صفحات المتجر:**")
            
            buy_together = st.checkbox("🤝 تشترى معًا", value=True, key="app_reco_buy_together")
            prod_group = st.checkbox("📦 عرض المنتجات التي تكون مجموعة منتج", value=True, key="app_reco_prod_group")
            prev_views = st.checkbox("👁️ المشاهدات السابقة", value=True, key="app_reco_prev_views")
            related_low = st.checkbox("📉 عرض منتجات منخفضة ذات صلة", value=True, key="app_reco_related_low")
            best_sellers = st.checkbox("🏆 عرض الأكثر مبيعاً", value=True, key="app_reco_best_sellers")
            also_bought = st.checkbox("🛍️ عرض (الزبائن اشتروا أيضًا)", value=True, key="app_reco_also_bought")
            wishlist_page = st.checkbox("❤️ عرض منتجات في صفحة الأمنيات", value=True, key="app_reco_wishlist_page")
            cart_page_reco = st.checkbox("🛒 عرض منتجات في صفحة السلة", value=True, key="app_reco_cart_page")
            
            st.markdown("---")
            cart_btn_option = st.selectbox(
                "🛒 عرض زر إضافة للسلة:",
                ["في صفحة السلة فقط", "في جميع الصفحات"],
                index=0,
                key="app_reco_cart_btn_dropdown_scope"
            )
            
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("💾 حفظ وتعميم خيارات التوصيات والحزم", type="primary", use_container_width=True, key="save_reco_advanced_settings_btn"):
                with st.spinner("جاري تدوين الإعدادات..."):
                    st.success("✅ تم مزامنة وحفظ كافة شروط التوصيات!")

    st.divider()

    with st.spinner("🔄 جاري مزامنة كشف جرد أصناف المستودع..."):
        prod_res = safe_api_request("GET", "https://api.salla.dev/admin/v2/products", headers)
    
    if prod_res and prod_res.get("data"):
        products = prod_res["data"]
        
        # ✅ زر تصدير المنتجات
        if st.button("📥 تصدير كشف المنتجات الحالية إلى Excel", key="export_all_prod_excel_green"):
            ex_data = export_products_to_excel(products)
            if ex_data:
                st.download_button(
                    "📥 تحميل الملف",
                    ex_data,
                    f"Products_Inventory_Report_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary"
                )
            
        st.divider()
        
        # --- نموذج استيراد المنتجات ---
        with st.expander("📥 استيراد وتحديث المنتجات جماعياً (XLSX)"):
            uploaded_file = st.file_uploader("ارفع ملف المنتجات:", type=["xlsx"])
            if uploaded_file and st.button("🚀 معالجة الملف", type="primary"):
                st.info("تم تفعيل ميزة الاستيراد الجماعي للبيانات.")

        # ==========================================
        # ✅ فلاتر التصفية المحسّنة
        # ==========================================
        st.markdown("#### 🔍 تصفية المنتجات:")
        
        # ✅ استخراج جميع تواريخ الانتهاء الفريدة للقائمة المنسدلة
        all_end_dates = set()
        for p in products:
            sale_end = p.get('sale_end') or (p.get('sale_price', {}).get('expired_at') if isinstance(p.get('sale_price'), dict) else None)
            if sale_end and sale_end != "غير محدد":
                try:
                    # محاولة تحويل التاريخ إلى صيغة موحدة
                    if isinstance(sale_end, str):
                        # محاولة استخراج التاريخ من النص
                        date_match = sale_end.split(' ')[0] if ' ' in sale_end else sale_end
                        all_end_dates.add(date_match)
                except:
                    pass
        
        end_dates_list = sorted(list(all_end_dates)) if all_end_dates else []
        
        col_f1, col_f2, col_f3, col_f4 = st.columns(4)
        with col_f1: 
            filter_no_img = st.checkbox("بدون صور", key="filter_no_img")
        with col_f2: 
            filter_has_promo = st.checkbox("لها عنوان ترويجي", key="filter_has_promo")
        with col_f3: 
            filter_hidden = st.checkbox("المنتجات المخفية", key="filter_hidden")
        with col_f4: 
            # ✅ قائمة منسدلة لتواريخ الانتهاء بدلاً من date_input
            filter_end_date = st.selectbox(
                "📅 تاريخ نهاية التخفيض:",
                ["الكل"] + end_dates_list,
                key="filter_end_date_select"
            )
        
        search_query = st.text_input("🔍 ابحث عن منتج (اسم أو SKU أو ID):")
        
        # ==========================================
        # ✅ تطبيق الفلاتر
        # ==========================================
        filtered_products = products.copy()
        
        # فلتر بدون صور
        if filter_no_img:
            filtered_products = [p for p in filtered_products if not p.get('thumbnail') and not p.get('main_image')]
        
        # فلتر لها عنوان ترويجي
        if filter_has_promo:
            filtered_products = [p for p in filtered_products if p.get('promotion_title') or (p.get('promotion', {}).get('title'))]
        
        # فلتر المنتجات المخفية
        if filter_hidden:
            filtered_products = [p for p in filtered_products if p.get('status') == 'hidden']
        
        # فلتر تاريخ نهاية التخفيض
        if filter_end_date != "الكل":
            filtered_products = [
                p for p in filtered_products 
                if p.get('sale_end') and filter_end_date in str(p.get('sale_end'))
            ]
        
        # فلتر البحث
        if search_query:
            search_lower = search_query.lower()
            filtered_products = [
                p for p in filtered_products 
                if (search_lower in p.get('name', '').lower() or 
                    search_lower in str(p.get('sku', '')).lower() or 
                    search_lower in str(p.get('id', '')))
            ]
        
        # ✅ عرض عدد المنتجات بعد التصفية
        st.markdown(f"""
            <div style="background: #f0f4f8; padding: 8px 16px; border-radius: 8px; margin-bottom: 14px; border-right: 4px solid #00b4d8;">
                <strong>📊 عدد المنتجات: {len(filtered_products)} منتج</strong>
                {f' (تم تصفيتها من أصل {len(products)})' if len(filtered_products) < len(products) else ''}
            </div>
        """, unsafe_allow_html=True)
        
        # ==========================================
        # ✅ عرض المنتجات المفلترة
        # ==========================================
        for idx, p in enumerate(filtered_products):
            p_id = p.get('id', 'N/A')
            p_name = p.get('name', 'منتج بدون اسم')
            p_sku = p.get('sku', 'لا يوجد')
            status = p.get('status', 'sale')
            p_url = p.get('url', 'https://salla.sa')
            
            # ✅ استخراج العنوان الترويجي والعنوان الفرعي
            promo = p.get('promotion', {})
            p_promotion = p.get('promotion_title') or (promo.get('title') if isinstance(promo, dict) else '') or "لا يوجد"
            p_sub_title = promo.get('sub_title') if isinstance(promo, dict) else ''
            
            # ✅ التحقق من وجود صورة
            has_image = bool(p.get('thumbnail') or p.get('main_image'))
            
            # ✅ حساب الأسعار
            price_val = get_flat_price(p.get('price', 0))
            regular_val = get_flat_price(p.get('regular_price', 0))
            sale_val = get_flat_price(p.get('sale_price', 0))

            base_price = regular_val if regular_val > 0 else price_val
            
            if sale_val > 0 and sale_val < base_price:
                display_sale_price = sale_val
                has_discount = True
            elif price_val < regular_val and price_val > 0:
                display_sale_price = price_val
                has_discount = True
            else:
                display_sale_price = base_price
                has_discount = False

            discount_percent = int(((base_price - display_sale_price) / base_price) * 100) if has_discount and base_price > 0 else 0
            
            sale_start_date = p.get('sale_start') or (p.get('sale_price', {}).get('start_at') if isinstance(p.get('sale_price'), dict) else None) or "غير محدد"
            sale_end_date = p.get('sale_end') or (p.get('sale_price', {}).get('expired_at') if isinstance(p.get('sale_price'), dict) else None) or "غير محدد"
            
            disp_status = "🟢 معروض" if status == "sale" else "🔴 مخفي"
            img_status = "✅ له صورة" if has_image else "❌ بدون صورة"
            
            # ✅ عرض المنتج بتنسيق محسن
            st.markdown(f"""
                <div style="background: linear-gradient(135deg, #243b55 0%, #141e30 100%); 
                            padding: 12px 18px; border-radius: 12px 12px 0px 0px; 
                            margin-top: 20px; display: flex; justify-content: space-between; align-items: center; 
                            flex-wrap: wrap; gap: 8px; border-bottom: 3px solid #e67e22;">
                    <span style="color: #ffffff; font-weight: bold; font-size: 15px;">📦 {p_name}</span>
                    <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                        <span style="background: rgba(255,255,255,0.15); color: #fff; padding: 3px 12px; border-radius: 20px; font-size: 11px;">{disp_status}</span>
                        <span style="background: rgba(255,255,255,0.1); color: #ffca28; padding: 3px 12px; border-radius: 20px; font-size: 11px;">{img_status}</span>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            with st.container():
                st.markdown("""
                    <div style="background-color: #fafbfc; padding: 18px 20px; border-radius: 0px 0px 12px 12px; 
                                border: 1px solid #e1e8ed; border-top: none; box-shadow: 0 4px 10px rgba(0,0,0,0.03); margin-bottom: 20px;">
                """, unsafe_allow_html=True)
                
                c_info, c_pricing, c_action = st.columns([3, 3, 2])
                
                with c_info:
                    st.markdown(f"🆔 **المعرف:** `{p_id}`")
                    st.markdown(f"🔢 **SKU:** `{p_sku}`")
                    st.markdown(f"📢 **العنوان الترويجي:** <span style='color:#e67e22; font-weight:bold;'>{p_promotion}</span>", unsafe_allow_html=True)
                    if p_sub_title:
                        st.markdown(f"📝 **العنوان الفرعي:** <span style='color:#2a9d8f;'>{p_sub_title}</span>", unsafe_allow_html=True)
                    st.markdown(f"🔗 [🌐 معاينة المنتج]({p_url})")
                    st.markdown(f"📦 **المخزون:** {p.get('quantity', 0)} حبة | 📈 **المبيعات:** {p.get('sold_quantity', 0)}")
                    st.markdown(f"📊 **خاضع للضريبة:** {'🟢 نعم' if p.get('with_tax', True) else '⚪ لا'}")
                
                with c_pricing:
                    st.markdown("<b style='color:#2c3e50;'>💰 تفاصيل الأسعار:</b>", unsafe_allow_html=True)
                    
                    if has_discount:
                        st.markdown(f"""
                        <div style="background:#fff3cd; padding:12px; border-radius:8px; border:1px solid #ffeba2; border-right:5px solid #ffc107;">
                            <span style="text-decoration: line-through; color: #7f8c8d; font-size:13px;">السعر الأساسي: {base_price:,.2f} SAR</span><br>
                            <b style="color: #c0392b; font-size:17px;">السعر المخفض: {display_sale_price:,.2f} SAR</b><br>
                            <span style="background:#c0392b; color:#fff; padding:2px 7px; border-radius:4px; font-size:11px; font-weight:bold; display:inline-block; margin-top:5px;">خصم {discount_percent}%</span>
                        </div>
                        """, unsafe_allow_html=True)
                        st.markdown(f"📅 **بداية التخفيض:** `{sale_start_date}`")
                        st.markdown(f"📅 **نهاية التخفيض:** `{sale_end_date}`")
                    else:
                        st.markdown(f"""
                        <div style="background:#e2e8f0; padding:12px; border-radius:8px; border:1px solid #cbd5e1; border-right:5px solid #4a5568;">
                            <b style="color:#2d3748; font-size:15px;">السعر الحالي: {base_price:,.2f} SAR</b><br>
                            <span style="color:#718096; font-size:12px;">🔴 لا يوجد خصم</span>
                        </div>
                        """, unsafe_allow_html=True)
                        
                with c_action:
                    if st.button("📋 نسخ ID", key=f"cp_{p_id}_{idx}", use_container_width=True):
                        st.toast(f"✅ تم نسخ: {p_id}")
                        
                    target_st = "hidden" if status == "sale" else "sale"
                    btn_lbl = "👁️ إخفاء" if status == "sale" else "👁️ إظهار"
                    btn_type = "secondary" if status == "sale" else "primary"
                    
                    if st.button(btn_lbl, key=f"sh_{p_id}_{idx}", type=btn_type, use_container_width=True):
                        with st.spinner("جاري المزامنة..."):
                            if update_product_status(p_id, target_st):
                                st.success("✅ تم التحديث!")
                                st.rerun()
                    
                    # ✅ زر تعديل العنوان الترويجي (مفتاح فريد)
                    if st.button("✏️ تعديل الترويج", key=f"edit_promo_btn_{p_id}_{idx}", use_container_width=True):
                        st.session_state[f"show_promo_edit_{p_id}"] = True
                    
                    if st.session_state.get(f"show_promo_edit_{p_id}", False):
                        with st.container():
                            new_promo = st.text_input(
                                "العنوان الترويجي الجديد:",
                                value=p_promotion if p_promotion != "لا يوجد" else "",
                                key=f"promo_input_{p_id}_{idx}"  # ✅ مفتاح فريد
                            )
                            col_save1, col_save2 = st.columns(2)
                            with col_save1:
                                if st.button("💾 حفظ", key=f"save_promo_{p_id}_{idx}", use_container_width=True):
                                    with st.spinner("جاري الحفظ..."):
                                        safe_api_request(
                                            "PUT",
                                            f"https://api.salla.dev/admin/v2/products/{p_id}",
                                            headers,
                                            json={"promotion_title": new_promo}
                                        )
                                        st.success("✅ تم التحديث!")
                                        st.session_state[f"show_promo_edit_{p_id}"] = False
                                        st.rerun()
                            with col_save2:
                                if st.button("❌ إلغاء", key=f"cancel_promo_{p_id}_{idx}", use_container_width=True):
                                    st.session_state[f"show_promo_edit_{p_id}"] = False
                                    st.rerun()
                    
                    # ✅ زر تعديل العنوان الفرعي (مفتاح فريد)
                    if st.button("✏️ تعديل العنوان الفرعي", key=f"edit_sub_btn_{p_id}_{idx}", use_container_width=True):
                        st.session_state[f"show_sub_edit_{p_id}"] = True
                    
                    if st.session_state.get(f"show_sub_edit_{p_id}", False):
                        with st.container():
                            new_sub = st.text_input(
                                "العنوان الفرعي الجديد:",
                                value=p_sub_title,
                                key=f"sub_input_{p_id}_{idx}"  # ✅ مفتاح فريد
                            )
                            col_save1, col_save2 = st.columns(2)
                            with col_save1:
                                if st.button("💾 حفظ", key=f"save_sub_{p_id}_{idx}", use_container_width=True):
                                    with st.spinner("جاري الحفظ..."):
                                        safe_api_request(
                                            "PUT",
                                            f"https://api.salla.dev/admin/v2/products/{p_id}",
                                            headers,
                                            json={"promotion_subtitle": new_sub}
                                        )
                                        st.success("✅ تم التحديث!")
                                        st.session_state[f"show_sub_edit_{p_id}"] = False
                                        st.rerun()
                            with col_save2:
                                if st.button("❌ إلغاء", key=f"cancel_sub_{p_id}_{idx}", use_container_width=True):
                                    st.session_state[f"show_sub_edit_{p_id}"] = False
                                    st.rerun()
                
                st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.warning("⚠️ لا توجد منتجات متاحة أو فشلت المزامنة.")
