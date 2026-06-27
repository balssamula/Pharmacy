import streamlit as st
import pandas as pd
from datetime import datetime
from utils import get_headers, safe_api_request, get_flat_price, update_product_status, export_products_to_excel

def render_products_page():
    st.markdown("<h2 style='color:#0f1c2e;'>📦 مركز إدارة المنتجات الذكي</h2>", unsafe_allow_html=True)
    
    headers = get_headers()
    if not headers: return

    # ==========================================
    # ✅ إعدادات المتجر المدمجة
    # ==========================================
    st.markdown("### ⚙️ إعدادات المتجر المدمجة")
    st.info("ℹ️ هذه الإعدادات تُطبق مباشرة على المتجر دون الحاجة لتثبيت تطبيقات خارجية.")
    
    col_widget1, col_widget2 = st.columns(2)

    # =========================================================================
    # ✅ 1. إعدادات المنتجات المقترحة
    # =========================================================================
    with col_widget1:
        with st.expander("🔄 إعدادات المنتجات المقترحة (شاهدتها مؤخراً)", expanded=False):
            st.markdown("#### 🛠️ إعدادات عرض المنتجات المقترحة")
            
            enable_recent = st.toggle("✅ تفعيل عرض المنتجات المقترحة", value=True, key="enable_recent_products")
            
            section_title = st.text_input("📝 عنوان القسم:", value="منتجات قد تعجبك", key="recent_section_title")
            
            st.markdown("**🎯 أماكن ظهور القسم:**")
            col_pos1, col_pos2 = st.columns(2)
            with col_pos1:
                show_home = st.checkbox("🏠 الصفحة الرئيسية", value=True, key="recent_show_home")
                show_categories = st.checkbox("📂 صفحة التصنيفات", value=True, key="recent_show_categories")
            with col_pos2:
                show_details = st.checkbox("📄 صفحة تفاصيل المنتج", value=True, key="recent_show_details")
                show_cart = st.checkbox("🛒 صفحة السلة", value=False, key="recent_show_cart")
            
            products_limit = st.slider("🔢 عدد المنتجات المعروضة:", min_value=2, max_value=20, value=6, step=1, key="recent_products_limit")
            
            if st.button("💾 تطبيق الإعدادات على المتجر", type="primary", use_container_width=True, key="apply_recent_settings"):
                with st.spinner("🔄 جاري تطبيق الإعدادات..."):
                    try:
                        settings_payload = {
                            "recent_products": {
                                "enabled": enable_recent,
                                "title": section_title,
                                "show_on": {
                                    "home": show_home,
                                    "categories": show_categories,
                                    "product_details": show_details,
                                    "cart": show_cart
                                },
                                "limit": products_limit
                            }
                        }
                        
                        response = safe_api_request(
                            "POST",
                            "https://api.salla.dev/admin/v2/settings/products",
                            headers,
                            json=settings_payload
                        )
                        
                        if response:
                            st.success("✅ تم تطبيق الإعدادات بنجاح على المتجر!")
                            st.balloons()
                        else:
                            st.error("❌ فشل تطبيق الإعدادات. تأكد من صلاحيات API.")
                    except Exception as e:
                        st.error(f"❌ خطأ: {str(e)}")

    # =========================================================================
    # ✅ 2. إعدادات التوصيات الذكية
    # =========================================================================
    with col_widget2:
        with st.expander("🧠 إعدادات نظام التوصيات الذكي", expanded=False):
            st.markdown("#### 🛠️ إعدادات توصيات المنتجات الذكية")
            
            enable_recommendations = st.toggle("✅ تفعيل نظام التوصيات", value=True, key="enable_recommendations")
            
            st.markdown("**🎯 أنواع التوصيات:**")
            
            col_rec1, col_rec2 = st.columns(2)
            with col_rec1:
                buy_together = st.checkbox("🤝 تشترى معًا", value=True, key="rec_buy_together")
                also_bought = st.checkbox("🛍️ الزبائن اشتروا أيضًا", value=True, key="rec_also_bought")
                best_sellers = st.checkbox("🏆 الأكثر مبيعاً", value=True, key="rec_best_sellers")
            with col_rec2:
                related_products = st.checkbox("🔗 منتجات ذات صلة", value=True, key="rec_related")
                recently_viewed = st.checkbox("👁️ شوهدت مؤخراً", value=True, key="rec_recently_viewed")
                top_rated = st.checkbox("⭐ الأعلى تقييماً", value=True, key="rec_top_rated")
            
            st.markdown("**🎯 أماكن ظهور التوصيات:**")
            col_pos3, col_pos4 = st.columns(2)
            with col_pos3:
                rec_show_home = st.checkbox("🏠 الصفحة الرئيسية", value=True, key="rec_show_home")
                rec_show_details = st.checkbox("📄 صفحة تفاصيل المنتج", value=True, key="rec_show_details")
            with col_pos4:
                rec_show_cart = st.checkbox("🛒 صفحة السلة", value=True, key="rec_show_cart")
                rec_show_checkout = st.checkbox("💳 صفحة الدفع", value=False, key="rec_show_checkout")
            
            recommendation_limit = st.slider("🔢 عدد التوصيات:", min_value=2, max_value=20, value=8, step=1, key="rec_limit")
            
            show_add_to_cart = st.radio(
                "🛒 عرض زر إضافة للسلة:",
                ["في جميع الصفحات", "في صفحة المنتج فقط", "عدم العرض"],
                index=0,
                key="rec_show_cart_btn"
            )
            
            if st.button("💾 تطبيق إعدادات التوصيات", type="primary", use_container_width=True, key="apply_rec_settings"):
                with st.spinner("🔄 جاري تطبيق إعدادات التوصيات..."):
                    try:
                        rec_payload = {
                            "recommendations": {
                                "enabled": enable_recommendations,
                                "types": {
                                    "buy_together": buy_together,
                                    "also_bought": also_bought,
                                    "best_sellers": best_sellers,
                                    "related": related_products,
                                    "recently_viewed": recently_viewed,
                                    "top_rated": top_rated
                                },
                                "show_on": {
                                    "home": rec_show_home,
                                    "product_details": rec_show_details,
                                    "cart": rec_show_cart,
                                    "checkout": rec_show_checkout
                                },
                                "limit": recommendation_limit,
                                "show_add_to_cart": show_add_to_cart
                            }
                        }
                        
                        response = safe_api_request(
                            "POST",
                            "https://api.salla.dev/admin/v2/settings/recommendations",
                            headers,
                            json=rec_payload
                        )
                        
                        if response:
                            st.success("✅ تم تطبيق إعدادات التوصيات بنجاح!")
                            st.balloons()
                        else:
                            st.error("❌ فشل تطبيق الإعدادات. تأكد من صلاحيات API.")
                    except Exception as e:
                        st.error(f"❌ خطأ: {str(e)}")

    st.divider()

    # ==========================================
    # ✅ معاينة المنتجات المقترحة
    # ==========================================
    with st.expander("👁️ معاينة المنتجات المقترحة (عرض حي)", expanded=False):
        st.markdown("#### 📊 المنتجات المقترحة حالياً")
        
        with st.spinner("🔄 جاري تحميل المنتجات المقترحة..."):
            rec_products_res = safe_api_request(
                "GET",
                "https://api.salla.dev/admin/v2/products/recommended",
                headers
            )
        
        if rec_products_res and rec_products_res.get("data"):
            rec_products = rec_products_res["data"]
            st.success(f"✅ عدد المنتجات المقترحة: {len(rec_products)}")
            
            cols = st.columns(min(len(rec_products), 4))
            for idx, product in enumerate(rec_products[:8]):
                with cols[idx % 4]:
                    st.markdown(f"""
                        <div style="background: #f8f9fa; border-radius: 10px; padding: 10px; 
                                    border: 1px solid #e8edf2; text-align: center; margin: 5px;">
                            <div style="font-size: 14px; font-weight: 600; color: #0f1c2e; 
                                        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                                {product.get('name', 'منتج')}
                            </div>
                            <div style="color: #00b4d8; font-weight: 700;">
                                {get_flat_price(product.get('price', 0)):,.2f} SAR
                            </div>
                            <div style="font-size: 11px; color: #6c757d;">
                                🛒 {product.get('sold_quantity', 0)} مبيعات
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
        else:
            st.info("ℹ️ لا توجد منتجات مقترحة حالياً. قم بتطبيق الإعدادات أعلاه.")

    st.divider()

    # ==========================================
    # ✅ استيراد وتحديث المنتجات (مع دعم العناوين)
    # ==========================================
    with st.expander("📥 استيراد وتحديث المنتجات جماعياً (XLSX)", expanded=False):
        st.markdown("#### 📤 استيراد المنتجات مع العناوين الترويجية والفرعية")
        
        # عرض الصيغة المطلوبة
        st.info("""
        📋 **الصيغة المطلوبة لملف المنتجات:**
        
        | المعرف (ID) | السعر (price) | العنوان الترويجي (promotion_title) | العنوان الفرعي (promotion_subtitle) | المخزون (quantity) | الحالة (status) |
        |--------------|---------------|-----------------------------------|-------------------------------------|--------------------|-----------------|
        | 12345 | 100 | عرض خاص | خصم 50% | 50 | sale |
        """)
        
        uploaded_file = st.file_uploader("ارفع ملف المنتجات (XLSX):", type=["xlsx"], key="import_products_file")
        
        if uploaded_file:
            try:
                df = pd.read_excel(uploaded_file)
                st.dataframe(df, use_container_width=True)
                st.info(f"✅ تم تحميل {len(df)} منتج")
                
                # ✅ عرض الأعمدة المتوقعة
                expected_cols = ['id', 'price', 'promotion_title', 'promotion_subtitle', 'quantity']
                missing_cols = [col for col in expected_cols if col not in df.columns]
                if missing_cols:
                    st.warning(f"⚠️ الأعمدة المفقودة: {', '.join(missing_cols)}")
                    st.info("💡 يمكنك استخدام الأعمدة الموجودة في ملفك: " + ", ".join(df.columns.tolist()))
                else:
                    st.success("✅ جميع الأعمدة المطلوبة موجودة")
                
                if st.button("🚀 معالجة وتحديث المنتجات", type="primary"):
                    with st.spinner("🔄 جاري تحديث المنتجات..."):
                        success_count = 0
                        error_count = 0
                        
                        for idx, row in df.iterrows():
                            try:
                                product_id = int(row.get('id', 0))
                                if product_id == 0:
                                    continue
                                
                                # بناء بيانات التحديث
                                update_payload = {}
                                
                                if pd.notna(row.get('promotion_title')):
                                    update_payload['promotion_title'] = str(row.get('promotion_title'))
                                
                                if pd.notna(row.get('promotion_subtitle')):
                                    update_payload['promotion_subtitle'] = str(row.get('promotion_subtitle'))
                                
                                if pd.notna(row.get('quantity')):
                                    update_payload['quantity'] = int(row.get('quantity'))
                                
                                if pd.notna(row.get('price')):
                                    update_payload['price'] = float(row.get('price'))
                                
                                if pd.notna(row.get('status')):
                                    update_payload['status'] = str(row.get('status'))
                                
                                # إرسال التحديث
                                if update_payload:
                                    response = safe_api_request(
                                        "PUT",
                                        f"https://api.salla.dev/admin/v2/products/{product_id}",
                                        headers,
                                        json=update_payload
                                    )
                                    if response:
                                        success_count += 1
                                    else:
                                        error_count += 1
                                        st.error(f"❌ فشل تحديث المنتج ID: {product_id}")
                            except Exception as e:
                                error_count += 1
                                st.error(f"❌ خطأ في الصف {idx+1}: {str(e)}")
                        
                        st.success(f"✅ تم تحديث {success_count} منتج بنجاح")
                        if error_count > 0:
                            st.warning(f"⚠️ فشل تحديث {error_count} منتج")
                        
                        if success_count > 0:
                            st.rerun()
            except Exception as e:
                st.error(f"❌ خطأ في قراءة الملف: {str(e)}")

    # ==========================================
    # ✅ استيراد وتحديث كميات الفروع
    # ==========================================
    with st.expander("🏪 استيراد وتحديث كميات الفروع (XLSX)", expanded=False):
        st.markdown("#### 🏪 تحديث كميات المنتجات في الفروع")
        
        st.info("""
        📋 **الصيغة المطلوبة لملف كميات الفروع:**
        
        | product_id | branch_id | quantity |
        |------------|-----------|----------|
        | 12345 | 1 | 30 |
        | 12345 | 2 | 20 |
        """)
        
        uploaded_branches_file = st.file_uploader("ارفع ملف كميات الفروع (XLSX):", type=["xlsx"], key="import_branches_file")
        
        if uploaded_branches_file:
            try:
                df_branches = pd.read_excel(uploaded_branches_file)
                st.dataframe(df_branches, use_container_width=True)
                st.info(f"✅ تم تحميل {len(df_branches)} سجل")
                
                expected_cols = ['product_id', 'branch_id', 'quantity']
                missing_cols = [col for col in expected_cols if col not in df_branches.columns]
                if missing_cols:
                    st.warning(f"⚠️ الأعمدة المفقودة: {', '.join(missing_cols)}")
                    st.info("💡 يمكنك استخدام الأعمدة الموجودة في ملفك: " + ", ".join(df_branches.columns.tolist()))
                else:
                    st.success("✅ جميع الأعمدة المطلوبة موجودة")
                
                if st.button("🚀 تحديث كميات الفروع", type="primary"):
                    with st.spinner("🔄 جاري تحديث كميات الفروع..."):
                        success_count = 0
                        error_count = 0
                        
                        for idx, row in df_branches.iterrows():
                            try:
                                product_id = int(row.get('product_id', 0))
                                branch_id = int(row.get('branch_id', 0))
                                quantity = int(row.get('quantity', 0))
                                
                                if product_id == 0 or branch_id == 0:
                                    continue
                                
                                # تحديث كمية المنتج في الفرع
                                branch_payload = {
                                    "quantity": quantity
                                }
                                
                                response = safe_api_request(
                                    "PUT",
                                    f"https://api.salla.dev/admin/v2/products/{product_id}/branches/{branch_id}",
                                    headers,
                                    json=branch_payload
                                )
                                if response:
                                    success_count += 1
                                else:
                                    error_count += 1
                                    st.error(f"❌ فشل تحديث المنتج {product_id} في الفرع {branch_id}")
                            except Exception as e:
                                error_count += 1
                                st.error(f"❌ خطأ في الصف {idx+1}: {str(e)}")
                        
                        st.success(f"✅ تم تحديث كميات {success_count} فرع بنجاح")
                        if error_count > 0:
                            st.warning(f"⚠️ فشل تحديث {error_count} فرع")
                        
                        if success_count > 0:
                            st.rerun()
            except Exception as e:
                st.error(f"❌ خطأ في قراءة الملف: {str(e)}")

    st.divider()

    # ==========================================
    # ✅ جلب وعرض المنتجات
    # ==========================================
    with st.spinner("🔄 جاري مزامنة كشف جرد أصناف المستودع..."):
        prod_res = safe_api_request("GET", "https://api.salla.dev/admin/v2/products", headers)
    
    if prod_res and prod_res.get("data"):
        products = prod_res["data"]
        
        # ==========================================
        # ✅ أزرار التصدير
        # ==========================================
        col_export1, col_export2, col_export3 = st.columns([1, 1, 4])
        with col_export1:
            if st.button("📥 تصدير كشف المنتجات الكامل", key="export_all_prod_excel_green"):
                ex_data = export_products_to_excel(products)
                if ex_data:
                    st.download_button(
                        "📥 تحميل الكشف الكامل",
                        ex_data,
                        f"Products_All_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="primary",
                        key="download_all_products"
                    )
        
        with col_export2:
            if st.button("📥 تصدير المنتجات المفلترة", key="export_filtered_products"):
                st.session_state["export_filtered_products"] = True
                st.rerun()
            
        st.divider()
        
        # ==========================================
        # ✅ فلاتر التصفية
        # ==========================================
        st.markdown("#### 🔍 تصفية المنتجات:")
        
        all_end_dates = set()
        for p in products:
            sale_end = p.get('sale_end') or (p.get('sale_price', {}).get('expired_at') if isinstance(p.get('sale_price'), dict) else None)
            if sale_end and sale_end != "غير محدد":
                try:
                    if isinstance(sale_end, str):
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
        
        if filter_no_img:
            filtered_products = [p for p in filtered_products if not p.get('thumbnail') and not p.get('main_image')]
        
        if filter_has_promo:
            filtered_products = [p for p in filtered_products if p.get('promotion_title') or (p.get('promotion', {}).get('title'))]
        
        if filter_hidden:
            filtered_products = [p for p in filtered_products if p.get('status') == 'hidden']
        
        if filter_end_date != "الكل":
            filtered_products = [
                p for p in filtered_products 
                if p.get('sale_end') and filter_end_date in str(p.get('sale_end'))
            ]
        
        if search_query:
            search_lower = search_query.lower()
            filtered_products = [
                p for p in filtered_products 
                if (search_lower in p.get('name', '').lower() or 
                    search_lower in str(p.get('sku', '')).lower() or 
                    search_lower in str(p.get('id', '')))
            ]
        
        # ✅ تصدير المنتجات المفلترة
        if st.session_state.get("export_filtered_products", False):
            if filtered_products:
                ex_data = export_products_to_excel(filtered_products)
                if ex_data:
                    st.download_button(
                        "📥 تحميل المنتجات المفلترة",
                        ex_data,
                        f"Products_Filtered_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="primary",
                        key="download_filtered_products"
                    )
                st.session_state["export_filtered_products"] = False
            else:
                st.warning("⚠️ لا توجد منتجات مطابقة للفلترة للتصدير")
                st.session_state["export_filtered_products"] = False
        
        # ✅ عرض عدد المنتجات
        st.markdown(f"""
            <div style="background: #f0f4f8; padding: 8px 16px; border-radius: 8px; margin-bottom: 14px; border-right: 4px solid #00b4d8;">
                <strong>📊 عدد المنتجات: {len(filtered_products)} منتج</strong>
                {f' (تم تصفيتها من أصل {len(products)})' if len(filtered_products) < len(products) else ''}
            </div>
        """, unsafe_allow_html=True)
        
        # ==========================================
        # ✅ عرض المنتجات
        # ==========================================
        for idx, p in enumerate(filtered_products):
            p_id = p.get('id', 'N/A')
            p_name = p.get('name', 'منتج بدون اسم')
            p_sku = p.get('sku', 'لا يوجد')
            status = p.get('status', 'sale')
            p_url = p.get('url', 'https://salla.sa')
            
            # ✅ استخراج العناوين بشكل صحيح
            promo = p.get('promotion', {})
            p_promotion = p.get('promotion_title') or (promo.get('title') if isinstance(promo, dict) else '') or "لا يوجد"
            p_sub_title = p.get('promotion_subtitle') or (promo.get('sub_title') if isinstance(promo, dict) else '')
            
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
            
            # ✅ حالات المنتج
            disp_status = "🟢 معروض" if status == "sale" else "🔴 مخفي"
            img_status = "✅ له صورة" if has_image else "❌ بدون صورة"
            tax_status = "🟢 خاضع للضريبة" if p.get('with_tax', True) else "⚪ معفى من الضريبة"

            # ✅ عرض المنتج مع جميع الحالات
            st.markdown(f"""
                <div style="background: linear-gradient(135deg, #243b55 0%, #141e30 100%); 
                            padding: 12px 18px; border-radius: 12px 12px 0px 0px; 
                            margin-top: 20px; display: flex; justify-content: space-between; align-items: center; 
                            flex-wrap: wrap; gap: 8px; border-bottom: 3px solid #e67e22;">
                    <span style="color: #ffffff; font-weight: bold; font-size: 15px;">📦 {p_name}</span>
                    <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                        <span style="background: rgba(255,255,255,0.15); color: #fff; padding: 3px 12px; border-radius: 20px; font-size: 11px;">{disp_status}</span>
                        <span style="background: rgba(255,255,255,0.1); color: #ffca28; padding: 3px 12px; border-radius: 20px; font-size: 11px;">{img_status}</span>
                        <span style="background: rgba(255,255,255,0.08); color: #a8d8ea; padding: 3px 12px; border-radius: 20px; font-size: 11px;">{tax_status}</span>
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
                    
                    # ✅ عرض العنوان الفرعي بشكل واضح
                    if p_sub_title:
                        st.markdown(f"📝 **العنوان الفرعي:** <span style='color:#2a9d8f; font-weight:bold;'>{p_sub_title}</span>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"📝 **العنوان الفرعي:** <span style='color:#6c757d;'>لا يوجد عنوان فرعي</span>", unsafe_allow_html=True)
                    
                    st.markdown(f"🔗 [🌐 معاينة المنتج]({p_url})")
                    st.markdown(f"📦 **المخزون:** {p.get('quantity', 0)} حبة | 📈 **المبيعات:** {p.get('sold_quantity', 0)}")
                    st.markdown(f"📊 **خاضع للضريبة:** {tax_status}")
                    
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
                    
                    # ✅ زر تعديل الترويج
                    if st.button("✏️ تعديل العنوان الترويجي", key=f"edit_promo_btn_{p_id}_{idx}", use_container_width=True):
                        st.session_state[f"show_promo_edit_{p_id}"] = True
                    
                    if st.session_state.get(f"show_promo_edit_{p_id}", False):
                        with st.container():
                            new_promo = st.text_input(
                                "العنوان الترويجي الجديد:",
                                value=p_promotion if p_promotion != "لا يوجد" else "",
                                key=f"promo_input_{p_id}_{idx}"
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
                    
                    # ✅ زر تعديل العنوان الفرعي
                    if st.button("✏️ تعديل العنوان الفرعي", key=f"edit_sub_btn_{p_id}_{idx}", use_container_width=True):
                        st.session_state[f"show_sub_edit_{p_id}"] = True
                    
                    if st.session_state.get(f"show_sub_edit_{p_id}", False):
                        with st.container():
                            new_sub = st.text_input(
                                "العنوان الفرعي الجديد:",
                                value=p_sub_title,
                                key=f"sub_input_{p_id}_{idx}"
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
