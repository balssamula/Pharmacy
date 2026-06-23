import streamlit as st
from utils import get_headers, safe_api_request, get_flat_price, update_product_status, export_products_to_excel

def render_products_page():
    st.markdown("<h2 style='color:#0f1c2e;'>📦 مركز جرد المستودع والمنتجات الذكي</h2>", unsafe_allow_html=True)
    
    headers = get_headers()
    if not headers: return

    with st.spinner("🔄 جاري تحميل وجلب بيانات مستودع المنتجات..."):
        prod_res = safe_api_request("GET", "https://api.salla.dev/admin/v2/products", headers)
    
    if prod_res and prod_res.get("data"):
        products = prod_res["data"]
        
        if st.button("📥 تصدير قائمة جرد مستودع صيدليات بلسم الحالية إلى Excel"):
            ex_data = export_products_to_excel(products)
            st.download_button("اضغط هنا لتنزيل كشف المنتجات الفوري", ex_data, "Balsem_Inventory_Report.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            
        st.divider()
        search_query = st.text_input("🔍 تصفية وبحث فوري برقم الـ SKU، مسمى الصنف، أو الـ ID المعرف:")
        
        for idx, p in enumerate(products):
            p_id = p.get('id', 'N/A')
            p_name = p.get('name', 'منتج بدون اسم')
            p_sku = p.get('sku', 'لا يوجد')
            status = p.get('status', 'sale')
            p_url = p.get('url', 'https://salla.sa')
            
            p_promotion = p.get('promotion_title', '')
            if not p_promotion and isinstance(p.get('promotion'), dict):
                p_promotion = p.get('promotion', {}).get('title', '')
            if not p_promotion:
                p_promotion = "لا يوجد عنوان ترويجي"
            
            if search_query and (search_query.lower() not in p_name.lower() and search_query not in str(p_sku) and search_query not in str(p_id)):
                continue
                
            # --- سحب وحساب تفاصيل التسعير الشاملة وفق وثيقة الأسعار في سلة ---
            price = get_flat_price(p.get('price', 0))
            sale_price = get_flat_price(p.get('sale_price', 0))
            regular_price = get_flat_price(p.get('regular_price', 0))
            
            # احتساب السعر الأساسي ومقارنته بالسعر المخفض بشكل دقيق
            base_price = regular_price if regular_price > 0 else price
            if sale_price > 0 and price < base_price:
                display_sale_price = price
            else:
                display_sale_price = sale_price

            has_discount = 0 < display_sale_price < base_price
            discount_percent = int(((base_price - display_sale_price) / base_price) * 100) if has_discount and base_price > 0 else 0
            
            disp_status = "🟢 معروض ومتاح حالياً بالمتجر" if status == "sale" else "🔴 مخفي ومؤرشف في المسودات"
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
                    st.markdown(f"🆔 **معرف المنتج الرقمي:** `{p_id}`")
                    st.markdown(f"🔢 **الرمز المخزني (SKU):** `{p_sku}`")
                    # معالجة وعرض وسم الـ HTML للعنوان الترويجي بشكل سليم دون ظهوره كأكواد نصية مقروءة
                    st.markdown(f"📢 **العنوان الترويجي الحالي للصنف:** <span style='color:#e67e22; font-weight:bold;'>{p_promotion}</span>", unsafe_allow_html=True)
                    st.markdown(f"🔗 **معاينة الصنف:** [🌐 تصفح رابط المنتج في المتجر]({p_url})")
                    st.markdown(f"📦 **مخزون المستودع الحركي:** `{p.get('quantity', 0)} حبة` | 📈 **المبيعات:** `{p.get('sold_quantity', 0)} قطعة`")
                
                with c_pricing:
                    st.markdown("<b style='color:#2c3e50;'>💰 هيكل وحاوية بيانات التسعير الشاملة:</b>", unsafe_allow_html=True)
                    
                    # إظهار وتفصيل السعر الأصلي والسعر المخفض ونسبة الخصم دائماً للمستخدم
                    st.markdown(f"""
                    <div style="background:#ffffff; padding:12px; border-radius:8px; border:1px solid #e2e8f0; border-right:5px solid #0f5132;">
                        <span style="color: #555; font-size:13px;">💵 السعر الأصلي الأساسي: <b>{base_price:,.2f} SAR</b></span><br>
                        <span style="color: #555; font-size:13px;">🏷️ السعر المخفض الحالي: <b>{display_sale_price:,.2f} SAR</b></span><br>
                        {"<span style='background:#d9534f; color:#fff; padding:2px 6px; border-radius:4px; font-size:11px; font-weight:bold; display:inline-block; margin-top:5px;'>🔥 نسبة التخفيض: " + str(discount_percent) + "% خصم</span>" if has_discount else "<span style='color:#888; font-size:11px; display:inline-block; margin-top:5px;'>🔴 لا يوجد خصم فعال حالياً</span>"}
                    </div>
                    """, unsafe_allow_html=True)
                        
                with c_action:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("📋 نسخ معرف الصنف السريع", key=f"cp_{p_id}_{idx}", use_container_width=True):
                        st.toast(f"✅ تم نسخ المعرف بنجاح: {p_id}")
                        
                    target_st = "hidden" if status == "sale" else "sale"
                    btn_lbl = "👁️ إخفاء الفوري من المتجر" if status == "sale" else "👁️ إظهار الفوري بالمتجر"
                    btn_type = "secondary" if status == "sale" else "primary"
                    
                    if st.button(btn_lbl, key=f"sh_{p_id}_{idx}", type=btn_type, use_container_width=True):
                        with st.spinner("جاري مزامنة حالة الظهور..."):
                            if update_product_status(p_id, target_st):
                                st.success("✅ تم تحديث ونشر ظهور المنتج بنجاح!")
                                st.rerun()
                                
                    with st.popover("✏️ تعديل الترويج"):
                        new_promo = st.text_input("أدخل مسمى العنوان الترويجي الجديد:", value=(p_promotion if p_promotion != "لا يوجد عنوان ترويجي" else ""), key=f"promo_input_{p_id}_{idx}")
                        if st.button("حفظ وتحديث الترويج", key=f"p_pr_btn_{p_id}_{idx}", type="primary", use_container_width=True):
                            with st.spinner("جاري حفظ العنوان..."):
                                safe_api_request("PUT", f"https://api.salla.dev/admin/v2/products/{p_id}", headers, json={"promotion_title": new_promo, "price": base_price})
                                st.success("✅ تم تحديث العنوان بنجاح!")
                                st.rerun()

                st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.warning("⚠️ لا توجد منتجات متاحة أو فشلت المزامنة.")
