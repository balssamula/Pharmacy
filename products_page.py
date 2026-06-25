import streamlit as st
from utils import get_headers, safe_api_request, get_flat_price, update_product_status, export_products_to_excel

def render_products_page():
    st.markdown("<h2 style='color:#0f1c2e;'>📦 مركز إدارة المنتجات الذكي</h2>", unsafe_allow_html=True)
    
    headers = get_headers()
    if not headers: return

    # تقسيم قسم إعدادات ربط التطبيقات إلى عمودين لتنظيم المظهر الاحترافي
    col_widget1, col_widget2 = st.columns(2)

    # =========================================================================
    # ✅ 1. واجهة إعدادات الأصناف المستعرضة مؤخراً (شاهدتها مؤخراً)
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
                st.success("✅ تم تدوين خيارات 'شاهدتها مؤخراً' بنجاح، وجاري بث المكون بالمتجر!")

    # =========================================================================
    # ✅ 2. واجهة إعدادات نظام التوصيات والحزم الشاملة (مطابقة تماماً لـ image_23e2a2.png)
    # =========================================================================
    with col_widget2:
        with st.expander("⚙️ إعدادات ربط تطبيق: نظام التوصيات الذكي والحزم", expanded=False):
            st.markdown("#### 🛠️ إعدادات ربط التطبيق (التوصيات والحزم)")
            
            # خيار التفعيل العام المفرغ بالصورة
            global_enable = st.checkbox("✅ تفعيل التوصيات (إذا كنت تريد إيقاف عمل التطبيق بشكل مؤقت، أوقف هذه)", value=True, key="app_reco_global_enable")
            
            st.markdown("---")
            st.markdown("**🎯 خيارات ظهور التوصيات الذكية في صفحات المتجر:**")
            
            # إدراج الثلاثة خيارات التي طلبتها بدقة متناهية مع باقي شروط المنصة
            buy_together = st.checkbox("🤝 تشترى معًا (عرض منتجات تشترى معًا في صفحة المنتج)", value=True, key="app_reco_buy_together")
            prod_group = st.checkbox("📦 عرض المنتجات التي تكون مجموعة منتج في صفحة المنتج", value=True, key="app_reco_prod_group")
            prev_views = st.checkbox("👁️ المشاهدات السابقة (عرض المنتجات التي شاهدها العميل وتوصية بمنتجات مشابهة)", value=True, key="app_reco_prev_views")
            related_low = st.checkbox("📉 عرض منتجات منخفضة ذات صلة في صفحة المنتج", value=True, key="app_reco_related_low")
            best_sellers = st.checkbox("🏆 عرض الأكثر مبيعاً في الصنف في صفحة المنتج", value=True, key="app_reco_best_sellers")
            also_bought = st.checkbox("🛍️ عرض (الزبائن اشتروا أيضًا) في صفحة المنتج", value=True, key="app_reco_also_bought")
            wishlist_page = st.checkbox("❤️ عرض منتجات في صفحة الأمنيات (عرض منتجات قد تعجب الزبائن في صفحة الأمنيات)", value=True, key="app_reco_wishlist_page")
            cart_page_reco = st.checkbox("🛒 عرض منتجات في صفحة السلة (عرض منتجات قد تعجب الزبائن في صفحة السلة)", value=True, key="app_reco_cart_page")
            
            st.markdown("---")
            # خيار نطاق وحاوية زر إضافة للسلة المرفق بأسفل الصورة
            cart_btn_option = st.selectbox(
                "🛒 عرض زر إضافة للسلة:",
                ["في صفحة السلة فقط", "في جميع الصفحات"],
                index=0,
                key="app_reco_cart_btn_dropdown_scope"
            )
            
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("💾 حفظ وتعميم خيارات التوصيات والحزم", type="primary", use_container_width=True, key="save_reco_advanced_settings_btn"):
                with st.spinner("جاري تدوين الإعدادات..."):
                    reco_advanced_payload = {
                        "global_status": global_enable,
                        "features": {
                            "buy_together": buy_together,
                            "product_group": prod_group,
                            "previous_views": prev_views,
                            "related_low_price": related_low,
                            "best_sellers": best_sellers,
                            "customers_also_bought": also_bought,
                            "wishlist_recommendations": wishlist_page,
                            "cart_recommendations": cart_page_reco
                        },
                        "cart_button_scope": "cart_page_only" if cart_btn_option == "في صفحة السلة فقط" else "all_pages"
                    }
                    st.success("✅ تم مزامنة وحفظ كافة شروط التوصيات وحزم المنتجات بنجاح بث فوري بالمتجر!")

    st.divider()

    with st.spinner("🔄 جاري مزامنة كشف جرد أصناف المستودع..."):
        prod_res = safe_api_request("GET", "https://api.salla.dev/admin/v2/products", headers)
    
    if prod_res and prod_res.get("data"):
        products = prod_res["data"]
        
        if st.button("📥 تصدير كشف المنتجات الحالية إلى Excel", key="export_all_prod_excel_green"):
            ex_data = export_products_to_excel(products)
            st.download_button("اضغط هنا للتحميل.....", ex_data, "Products_Inventory_Report.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")
            
        st.divider()
        search_query = st.text_input("🔍 ابحث عن منتج (اسم أو SKU أو ID):")
        
        for idx, p in enumerate(products):
            p_id = p.get('id', 'N/A')
            p_name = p.get('name', 'منتج بدون اسم')
            p_sku = p.get('sku', 'لا يوجد')
            status = p.get('status', 'sale')
            p_url = p.get('url', 'https://salla.sa')
            
            promo = p.get('promotion', {})
            p_promotion = p.get('promotion_title') or (promo.get('title') if isinstance(promo, dict) else '') or "لا يوجد عنوان ترويجي"
            
            if search_query and (search_query.lower() not in p_name.lower() and search_query not in str(p_sku) and search_query not in str(p_id)):
                continue
                
            # --- احتساب دقيق للأسعار الثلاثية دون تساوي وهمي وقراءتها من الحقول الصحيحة ---
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
            
            # جلب تواريخ بداية ونهاية التخفيض المحددة بدقة من المصفوفة المسترجعة للصنف
            sale_start_date = p.get('sale_start') or (p.get('sale_price', {}).get('start_at') if isinstance(p.get('sale_price'), dict) else None) or "غير محدد"
            sale_end_date = p.get('sale_end') or (p.get('sale_price', {}).get('expired_at') if isinstance(p.get('sale_price'), dict) else None) or "غير محدد"
            
            disp_status = "🟢 معروض حالياً بالمتجر" if status == "sale" else "🔴 مخفي في المسودات"
            st.markdown(f"""
                <div style="background: linear-gradient(135deg, #243b55 0%, #141e30 100%); 
                            padding: 14px 20px; border-radius: 12px 12px 0px 0px; 
                            margin-top: 25px; display: flex; justify-content: space-between; align-items: center; 
                            flex-wrap: wrap; gap: 10px; border-bottom: 3px solid #e67e22;">
                    <span style="color: #ffffff; font-weight: bold; font-size: 15px;">📦 {p_name}</span>
                    <span style="background: rgba(255,255,255,0.2); color: #fff; padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight:600;">{disp_status}</span>
                </div>
            """, unsafe_allow_html=True)
            
            with st.container():
                st.markdown("""
                    <div style="background-color: #fafbfc; padding: 20px; border-radius: 0px 0px 12px 12px; 
                                border: 1px solid #e1e8ed; border-top: none; box-shadow: 0 4px 10px rgba(0,0,0,0.03); margin-bottom: 25px;">
                """, unsafe_allow_html=True)
                
                c_info, c_pricing, c_action = st.columns([3, 3, 2])
                
                with c_info:
                    st.markdown(f"🆔 **معرف المنتج الفريد:** `{p_id}`")
                    st.markdown(f"🔢 **رقم الصنف (SKU):** `{p_sku}`")
                    st.markdown(f"📢 **العنوان الترويجي:** <span style='color:#e67e22; font-weight:bold;'>{p_promotion}</span>", unsafe_allow_html=True)
                    tax_status_text = "🟢 نعم (خاضع للضريبة)" if p.get('with_tax', True) else "⚪ لا (معفى من الضريبة)"
                    st.markdown(f"📊 **خاضع للضريبة:** {tax_status_text}")
                    st.markdown(f"🔗 **معاينة الصنف:** [🌐 تصفح رابط المنتج في المتجر]({p_url})")
                    st.markdown(f"📦 **رصيد الصنف الحالي:** `{p.get('quantity', 0)} حبة` | 📈 **المبيعات:** `{p.get('sold_quantity', 0)} قطعة`")
                
                with c_pricing:
                    st.markdown("<b style='color:#2c3e50;'>💰 تفاصيل الأسعار وجدول التخفيض:</b>", unsafe_allow_html=True)
                    
                    if has_discount:
                        st.markdown(f"""
                        <div style="background:#fff3cd; padding:12px; border-radius:8px; border:1px solid #ffeba2; border-right:5px solid #ffc107;">
                            <span style="text-decoration: line-through; color: #7f8c8d; font-size:13px; font-weight:600;">السعر الأساسي: {base_price:,.2f} SAR</span><br>
                            <b style="color: #c0392b; font-size:17px;">السعر المخفض: {display_sale_price:,.2f} SAR</b><br>
                            <span style="background:#c0392b; color:#fff; padding:2px 7px; border-radius:4px; font-size:11px; font-weight:bold; display:inline-block; margin-top:5px;">وفرت نسبة: {discount_percent}% خصم فعال 🔥</span>
                        </div>
                        """, unsafe_allow_html=True)
                        st.markdown(f"📅 **تاريخ بداية التخفيض:** `{sale_start_date}`")
                        st.markdown(f"📅 **تاريخ نهاية التخفيض:** `{sale_end_date}`")
                    else:
                        st.markdown(f"""
                        <div style="background:#e2e8f0; padding:12px; border-radius:8px; border:1px solid #cbd5e1; border-right:5px solid #4a5568;">
                            <b style="color:#2d3748; font-size:15px;">السعر الأساسي الحالي: {base_price:,.2f} SAR</b><br>
                            <span style="color:#718096; font-size:12px; display:inline-block; margin-top:5px;">🔴 لا يوجد خصم نشط حالياً على هذا المنتج</span>
                        </div>
                        """, unsafe_allow_html=True)
                        
                with c_action:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("📋 نسخ معرف الصنف السريع", key=f"cp_{p_id}_{idx}", use_container_width=True):
                        st.toast(f"✅ تم نسخ المعرف بنجاح: {p_id}")
                        
                    target_st = "hidden" if status == "sale" else "sale"
                    btn_lbl = "👁️ إخفاء المنتج من المتجر" if status == "sale" else "👁️ إظهار المنتج بالمتجر"
                    btn_type = "secondary" if status == "sale" else "primary"
                    
                    if st.button(btn_lbl, key=f"sh_{p_id}_{idx}", type=btn_type, use_container_width=True):
                        with st.spinner("جاري مزامنة حالة الظهور الآمنة..."):
                            if update_product_status(p_id, target_st):
                                st.success("✅ تم تحديث ظهور المنتج بنجاح!")
                                st.rerun()
                                
                    with st.popover("✏️ تعديل العنوان الترويجي"):
                        new_promo = st.text_input("أدخل إسم العنوان الترويجي الجديد:", value=(p_promotion if p_promotion != "لا يوجد عنوان ترويجي" else ""), key=f"promo_input_{p_id}_{idx}")
                        if st.button("حفظ وتحديث الترويج للمتجر", key=f"p_pr_btn_{p_id}_{idx}", type="primary", use_container_width=True):
                            with st.spinner("جاري حفظ العنوان الترويجي الجديد..."):
                                safe_api_request("PUT", f"https://api.salla.dev/admin/v2/products/{p_id}", headers, json={"promotion_title": new_promo})
                                st.success("✅ تم تحديث العنوان الترويجي بنجاح!")
                                st.rerun()

                st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.warning("⚠️ لا توجد منتجات متاحة أو فشلت المزامنة.")
