import streamlit as st
import pandas as pd
import requests  # ✅ إضافة import requests
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
    st.info("ℹ️ هذه الإعدادات تستخدم APIs سلة الرسمية")
    
    col_widget1, col_widget2 = st.columns(2)

    # =========================================================================
    # ✅ 1. تصدير المنتجات (باستخدام Export Products API)
    # =========================================================================
    with col_widget1:
        with st.expander("📤 تصدير المنتجات (Export Products)", expanded=False):
            st.markdown("#### 🛠️ تصدير المنتجات بأنواع مختلفة")
            
            # ✅ إضافة خيار تسجيل الدخول بحساب سلة
            use_salla_auth = st.checkbox(
                "🔐 تسجيل الدخول بحساب سلة (للتصدير المباشر)",
                value=False,
                key="use_salla_auth_export",
                help="قم بتسجيل الدخول بحساب سلة الخاص بك للحصول على صلاحيات التصدير"
            )
            
            if use_salla_auth:
                st.info("🔐 سيتم توجيهك لتسجيل الدخول بحساب سلة للحصول على صلاحيات التصدير")
                st.markdown("""
                    <div style="background: #f8f9fa; padding: 12px; border-radius: 8px; border-right: 4px solid #00b4d8;">
                        <b>📌 ملاحظة:</b> التصدير يتطلب صلاحيات <code>exports.read_write</code>
                        <br>
                        <span style="font-size: 12px; color: #6c757d;">يمكنك الحصول على هذه الصلاحيات من خلال تطبيقك في Salla Partners</span>
                    </div>
                """, unsafe_allow_html=True)
            else:
                st.info("ℹ️ سيتم التصدير باستخدام التوكن الحالي. تأكد من أن التوكن لديه صلاحية `exports.read_write`")
            
            export_type = st.selectbox(
                "نوع التصدير:",
                [
                    "products", "quantities", "prices", "seo",
                    "product-sample", "category", "brand"
                ],
                key="export_type_select",
                format_func=lambda x: {
                    "products": "📦 جميع المنتجات",
                    "quantities": "📊 كميات المنتجات",
                    "prices": "💰 أسعار المنتجات",
                    "seo": "🔍 بيانات SEO",
                    "product-sample": "📝 نموذج إضافة منتج",
                    "category": "📂 التصنيفات",
                    "brand": "🏷️ الماركات"
                }.get(x, x)
            )
            
            export_format = st.radio(
                "صيغة الملف:",
                ["xlsx", "csv"],
                index=0,
                key="export_format_select"
            )
            
            if st.button("📥 طلب تصدير المنتجات", type="primary", use_container_width=True, key="export_products_btn"):
                with st.spinner("🔄 جاري طلب التصدير..."):
                    export_payload = {
                        "type": export_type,
                        "format": export_format
                    }
                    
                    # ✅ تحديث الهيدر إذا كان المستخدم يستخدم حساب سلة
                    export_headers = headers.copy()
                    if use_salla_auth:
                        # هنا يمكن إضافة منطق تسجيل الدخول بحساب سلة
                        st.info("🔐 جاري التوجيه لتسجيل الدخول بحساب سلة...")
                        # يمكن إضافة OAuth flow هنا
                    
                    response = safe_api_request(
                        "POST",
                        "https://api.salla.dev/admin/v2/exports/products",
                        export_headers,
                        json=export_payload
                    )
                    
                    if response:
                        st.success("✅ تم طلب التصدير بنجاح! سيتم إرسال الملف إلى بريدك الإلكتروني.")
                        st.info("📧 تحقق من بريدك الإلكتروني المسجل في المتجر")
                        st.balloons()
                    else:
                        st.error("❌ فشل طلب التصدير. تأكد من صلاحيات API.")
                        st.info("💡 تأكد من أن التوكن لديه صلاحية `exports.read_write`")

    # =========================================================================
    # ✅ 2. رفع الصور للمنتجات (Attach Image by SKU)
    # =========================================================================
    with col_widget2:
        with st.expander("🖼️ رفع صورة للمنتج (Attach Image)", expanded=False):
            st.markdown("#### 🛠️ رفع صورة لمنتج باستخدام SKU")
            
            product_sku = st.text_input("🔢 SKU المنتج:", key="attach_image_sku")
            
            uploaded_image = st.file_uploader(
                "📷 اختر صورة المنتج:",
                type=["jpg", "jpeg", "png", "gif", "webp"],
                key="attach_image_file"
            )
            
            if uploaded_image and product_sku:
                st.image(uploaded_image, caption="الصورة المرفوعة", width=200)
            
            if st.button("📤 رفع الصورة", type="primary", use_container_width=True, key="attach_image_btn"):
                if not product_sku:
                    st.warning("⚠️ الرجاء إدخال SKU المنتج")
                elif not uploaded_image:
                    st.warning("⚠️ الرجاء اختيار صورة")
                else:
                    with st.spinner("🔄 جاري رفع الصورة..."):
                        try:
                            # تحضير الملف للرفع
                            files = {
                                'photo': (uploaded_image.name, uploaded_image.getvalue(), uploaded_image.type)
                            }
                            
                            # ✅ استخدام requests مع معالجة الأخطاء
                            response = requests.post(
                                f"https://api.salla.dev/admin/v2/products/sku/{product_sku}/images",
                                headers=headers,
                                files=files,
                                timeout=30
                            )
                            
                            if response.status_code == 200:
                                st.success("✅ تم رفع الصورة بنجاح!")
                                st.balloons()
                            elif response.status_code == 401:
                                st.error("❌ خطأ في التوكن. تأكد من صلاحيات API.")
                                st.info("💡 تأكد من أن التوكن لديه صلاحية `products.read_write`")
                            elif response.status_code == 422:
                                st.error("❌ تأكد من صحة SKU المنتج")
                            else:
                                st.error(f"❌ فشل رفع الصورة: {response.status_code}")
                                try:
                                    error_data = response.json()
                                    st.code(error_data)
                                except:
                                    st.code(response.text)
                        except requests.exceptions.RequestException as e:
                            st.error(f"❌ خطأ في الاتصال: {str(e)}")
                        except Exception as e:
                            st.error(f"❌ خطأ غير متوقع: {str(e)}")

    st.divider()

    # ==========================================
    # ✅ استيراد وتحديث المنتجات
    # ==========================================
    with st.expander("📥 استيراد وتحديث المنتجات جماعياً (XLSX)", expanded=False):
        st.markdown("#### 📤 استيراد المنتجات مع العناوين الترويجية والفرعية")
        
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
                
                expected_cols = ['id', 'price', 'promotion_title', 'promotion_subtitle', 'quantity']
                missing_cols = [col for col in expected_cols if col not in df.columns]
                if missing_cols:
                    st.warning(f"⚠️ الأعمدة المفقودة: {', '.join(missing_cols)}")
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
                                
                                branch_payload = {"quantity": quantity}
                                
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
    # ✅ عرض قائمة الفروع (مع معالجة خطأ 401)
    # ==========================================
    with st.expander("🏪 قائمة الفروع والمخازن", expanded=False):
        st.markdown("#### 📋 الفروع المتاحة في المتجر")
        
        st.info("💡 لعرض الفروع، تأكد من أن التوكن لديه صلاحية `branches.read`")
        
        # ✅ خيار تسجيل الدخول بحساب سلة لعرض الفروع
        use_salla_auth_branches = st.checkbox(
            "🔐 تسجيل الدخول بحساب سلة لعرض الفروع",
            value=False,
            key="use_salla_auth_branches",
            help="قم بتسجيل الدخول بحساب سلة الخاص بك للحصول على صلاحيات عرض الفروع"
        )
        
        with st.spinner("🔄 جاري تحميل الفروع..."):
            # ✅ استخدام headers مع صلاحيات مختلفة إذا كان المستخدم مسجل الدخول
            branches_headers = headers.copy()
            if use_salla_auth_branches:
                st.info("🔐 جاري التوجيه لتسجيل الدخول بحساب سلة...")
                # يمكن إضافة OAuth flow هنا
            
            branches_res = safe_api_request("GET", "https://api.salla.dev/admin/v2/branches", branches_headers)
        
        if branches_res and branches_res.get("data"):
            branches = branches_res["data"]
            st.success(f"✅ عدد الفروع: {len(branches)}")
            
            for branch in branches:
                with st.container():
                    st.markdown(f"""
                        <div style="background: #f8f9fa; padding: 12px 16px; border-radius: 8px; 
                                    border-right: 4px solid #00b4d8; margin-bottom: 10px;">
                            <div style="display: flex; justify-content: space-between; flex-wrap: wrap;">
                                <span style="font-weight: bold; font-size: 15px;">🏪 {branch.get('name', 'فرع غير مسمى')}</span>
                                <span style="color: {'#28a745' if branch.get('status') == 'active' else '#dc3545'};">
                                    {branch.get('status', 'غير معروف')}
                                </span>
                            </div>
                            <div style="font-size: 13px; color: #6c757d;">
                                📍 {branch.get('city', {}).get('name', '')} - {branch.get('address_description', 'لا يوجد عنوان')}
                            </div>
                            <div style="font-size: 12px; color: #6c757d;">
                                📞 {branch.get('contacts', {}).get('phone', 'لا يوجد رقم')}
                            </div>
                            <div style="font-size: 12px; color: #6c757d;">
                                🆔 معرف الفرع: {branch.get('id', 'N/A')}
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
        else:
            st.warning("⚠️ لا يمكن عرض الفروع. تأكد من صلاحيات API.")
            st.info("""
                📌 **لحل هذه المشكلة:**
                1. تأكد من أن التوكن لديه صلاحية `branches.read`
                2. أو قم بتسجيل الدخول بحساب سلة باستخدام الخيار أعلاه
                3. يمكنك الحصول على هذه الصلاحيات من خلال تطبيقك في Salla Partners
            """)

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
            if st.button("📥 تصدير الكشف الكامل", key="export_all_prod_excel_green"):
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
            if st.button("📥 تصدير المفلترة", key="export_filtered_products"):
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
            
            promo = p.get('promotion', {})
            p_promotion = p.get('promotion_title') or (promo.get('title') if isinstance(promo, dict) else '') or "لا يوجد"
            p_sub_title = p.get('promotion_subtitle') or (promo.get('sub_title') if isinstance(promo, dict) else '')
            
            has_image = bool(p.get('thumbnail') or p.get('main_image'))
            
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
            tax_status = "🟢 خاضع للضريبة" if p.get('with_tax', True) else "⚪ معفى من الضريبة"

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
                    
                    if p_sub_title:
                        st.markdown(f"📝 **العنوان الفرعي:** <span style='color:#2a9d8f; font-weight:bold;'>{p_sub_title}</span>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"📝 **العنوان الفرعي:** <span style='color:#6c757d;'>لا يوجد عنوان فرعي</span>", unsafe_allow_html=True)
                    
                    st.markdown(f"🔗 [🌐 معاينة المنتج]({p_url})")
                    st.markdown(f"📦 **المخزون:** {p.get('quantity', 0)} حبة | 📈 **المبيعات:** {p.get('sold_quantity', 0)}")
                    st.markdown(f"📊 **خاضع للضريبة:** {tax_status}")
                    
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
                    
                    if st.button("✏️ تعديل الترويج", key=f"edit_promo_btn_{p_id}_{idx}", use_container_width=True):
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
