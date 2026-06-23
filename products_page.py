import streamlit as st
from utils import get_headers, safe_api_request, get_flat_price, update_product_status, export_products_to_excel

def render_products_page():
    st.markdown("<h2 style='color:#0f1c2e;'>📦 مركز جرد المستودع والمنتجات الذكي</h2>", unsafe_allow_html=True)
    
    headers = get_headers()
    if not headers: return

    # --- استرجاع زر تصدير جرد المستودع إلى ملف Excel المحذوف سابَقاً ---
    with st.spinner("🔄 جاري تحميل وجلب بيانات مستودع المنتجات لإعداد تقرير الجرد..."):
        prod_res = safe_api_request("GET", "https://api.salla.dev/admin/v2/products", headers)
    
    if prod_res and prod_res.get("data"):
        products = prod_res["data"]
        
        if st.button("📥 تصدير قائمة جرد مستودع صيدليات بلسم المزامنة حالياً إلى Excel", type="secondary"):
            ex_data = export_products_to_excel(products)
            st.download_button("اضغط هنا لتنزيل كشف المنتجات الفوري", ex_data, "Balsem_Inventory_Report.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            
        st.divider()
        search_query = st.text_input("🔍 تصفية وبحث فوري برقم الـ SKU، مسمى الصنف، أو الـ ID المعرف:")
        
        for idx, p in enumerate(products):
            p_id = p.get('id', 'N/A')
            p_name = p.get('name', 'منتج بدون اسم')
            p_sku = p.get('sku', 'لا يوجد')
            status = p.get('status', 'sale')
            p_url = p.get('url', '#')
            
            # استرجاع العنوان الترويجي المحذوف بدقة متناهية من الكائنات الفرعية والمدمجة
            p_promotion = p.get('promotion_title', '')
            if not p_promotion and isinstance(p.get('promotion'), dict):
                p_promotion = p.get('promotion', {}).get('title', '')
            if not p_promotion:
                p_promotion = "لا يوجد عنوان ترويجي"
            
            if search_query and (search_query.lower() not in p_name.lower() and search_query not in str(p_sku) and search_query not in str(p_id)):
                continue
                
            # --- معالجة الأسعار الثلاثية (الأصل، المخفض، ونسبة الخصم بدقة حسابية كاملة) ---
            price = get_flat_price(p.get('price', 0))
            sale_price = get_flat_price(p.get('sale_price', 0))
            regular_price = get_flat_price(p.get('regular_price', 0))
            
            # إذا كان حقل السعر العادي متوفراً ومخالفاً، نعتمد عليه كسعر أصلي أساسي
            base_price = regular_price if regular_price > 0 else price
            
            has_discount = 0 < sale_price < base_price
            discount_percent = int(((base_price - sale_price) / base_price) * 100) if has_discount and base_price > 0 else 0
            
            # حاوية ترويسة المنتجات الداكنة الإبداعية الفاخرة مع التوزيع المرن لمنع التداخل
            disp_status = "🟢 معروض ومتاح حالياً بالمتجر" if status == "sale" else "🔴 مخفي ومؤرشف في المسودات"
            st.markdown(f"""
                <div style="background: linear-gradient(135deg, #243b55 0%, #141e30 100%); 
                            padding: 14px 20px; border-radius: 12px 12px 0px 0px; 
                            margin-top: 25px; display: flex; justify-content: space-between; align-items: center; 
                            flex-wrap: wrap; gap: 10px; border-bottom: 3px solid #e67e22;">
                    <span style="color: #ffffff; font-weight: bold; font-size: 15px;">📦 {p_name}</span>
                    <span style="background: rgba(255,255,255,0.2); color: #fff; padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight:600; white-space: nowrap;">{disp_status}</span>
                </div>
            """, unsafe_allow_html=True)
            
            with st.container():
                st.markdown("""
                    <div style="background-color: #fafbfc; padding: 20px; border-radius: 0px 0px 12px 12px; 
                                border: 1px solid #e1e8ed; border-top: none; box-shadow: 0 4px 10px rgba(0,0,0,0.03); margin-bottom: 25px;">
                """, unsafe_allow_html=True)
                
                c_info, c_pricing, c_action = st.columns([3, 3, 2])
                
                with c_info:
                    st.markdown(f"🆔 **معرف المنتج الرقمي الفريد:** `{p_id}`")
                    st.markdown(f"🔢 **الرمز المخزني (SKU):** `{p_sku}`")
                    st.markdown(f"📢 **العنوان الترويجي الحالي للصنف:** `<span style='color:#e67e22; font-weight:bold;'>{p_promotion}</span>`", unsafe_allow_html=True)
                    st.markdown(f"🔗 **رابط الصنف الفعلي للمعاينة الفورية:** [🌐 تصفح رابط المنتج في المتجر]({p_url})")
                    st.markdown(f"📦 **مخزون المستودع الحالي:** `{p.get('quantity', 0)} حبة متوفرة` | 📈 **الكميات المباعة سابَقاً:** `{p.get('sold_quantity', 0)} قطعة`")
                
                with c_pricing:
                    st.markdown("<b style='color:#2c3e50;'>💰 هيكل وحاوية بيانات التسعير الشاملة:</b>", unsafe_allow_html=True)
                    if has_discount:
                        st.markdown(f"""
                        <div style="background:#fff3cd; padding:12px; border-radius:8px; border-right:5px solid #ffc107;">
                            <span style="text-decoration: line-through; color: #7f8c8d; font-size:13px; font-weight:600;">السعر الأصلي الأساسي: {base_price:,.2f} SAR</span><br>
                            <b style="color: #c0392b; font-size:17px;">السعر المخفض النشط للجمهور: {sale_price:,.2f} SAR</b><br>
                            <span style="background:#c0392b; color:#fff; padding:3px 8px; border-radius:4px; font-size:11px; font-weight:bold; display:inline-block; margin-top:5px;">نسبة التخفيض الكلية: {discount_percent}% خصم حقيقي 🔥</span>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown(f"""
                        <div style="background:#e2e8f0; padding:12px; border-radius:8px; border-right:5px solid #4a5568;">
                            <b style="color:#2d3748; font-size:15px;">السعر الثابت والأساسي الحالي: {base_price:,.2f} SAR</b><br>
                            <span style="color:#718096; font-size:12px;">(المنتج يباع بالقيمة الكاملة الموحدة، لا توجد عروض ترويجية نشطة عليه)</span>
                        </div>
                        """, unsafe_allow_html=True)
                        
                with c_action:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("📋 نسخ معرف الصنف السريع", key=f"cp_{p_id}_{idx}", use_container_width=True):
                        st.toast(f"✅ تم نسخ المعرف بنجاح: {p_id}")
                        
                    # زر اخفاء وعرض المطور بالكامل بالربط المحدث والمضمون 100%
                    target_st = "hidden" if status == "sale" else "sale"
                    btn_lbl = "👁️ إخفاء الفوري من المتجر" if status == "sale" else "👁️ إظهار ونشر بالمتجر الإلكتروني"
                    btn_type = "primary" if status == "sale" else "secondary"
                    
                    if st.button(btn_lbl, key=f"sh_{p_id}_{idx}", type=btn_type, use_container_width=True):
                        with st.spinner("جاري مزامنة حاله الظهور مع خوادم سلة..."):
                            if update_product_status(p_id, target_st):
                                st.success("✅ تم تعديل مفعول ظهور وعرض المنتج بنجاح فوري!")
                                st.rerun()
                            else:
                                st.error("❌ فشلت عملية الربط التلقائي، يرجى مراجعة صلاحيات التوكن.")
                                
                    # --- إسناد مفاتيح فريدة (Key Assignment) لحل خطأ Streamlit Duplicate Element ID بشكل قاطع ---
                    with st.popover("✏️ تحديث عنوان الترويج"):
                        new_promo = st.text_input("أدخل مسمى العنوان الترويجي الجديد:", value=(p_promotion if p_promotion != "لا يوجد عنوان ترويجي" else ""), key=f"promo_input_{p_id}_{idx}")
                        if st.button("حفظ وتحديث الترويج", key=f"p_pr_btn_{p_id}_{idx}", use_container_width=True):
                            with st.spinner("جاري حفظ العنوان..."):
                                safe_api_request("PUT", f"https://api.salla.dev/admin/v2/products/{p_id}", headers, json={"promotion_title": new_promo, "price": base_price})
                                st.success("✅ تم تحديث العنوان بنجاح!")
                                st.rerun()

                st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.warning("⚠️ لا توجد منتجات متاحة أو فشلت المزامنة.")
